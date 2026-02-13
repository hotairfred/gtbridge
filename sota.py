"""
SOTA (Summits on the Air) spot fetcher.

Polls the SOTA API for active activators and feeds them into the bridge
as DXSpot objects, so they appear in GridTracker's call roster with
"CQ SOTA" in the message text.

Summit grids are looked up from the SOTA summit API and cached locally
so bearings point to the actual mountain, not the operator's home QTH.

API endpoints (no auth required):
  Spots: https://api2.sota.org.uk/api/spots/50/all
  Summit: https://api2.sota.org.uk/api/summits/{association}/{code}
"""

import asyncio
import json
import logging
import os
import time
import urllib.request
from typing import Callable, Optional

log = logging.getLogger('sota')

SOTA_SPOTS_URL = 'https://api2.sota.org.uk/api/spots/50/all'
SOTA_SUMMIT_URL = 'https://api2.sota.org.uk/api/summits'

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sota_cache.json')


class SOTAFetcher:
    """Periodically fetches SOTA spots and delivers them via callback."""

    def __init__(self, on_spot: Callable, poll_interval: int = 120,
                 mode_filter: Optional[set] = None,
                 band_filter: Optional[set] = None,
                 spot_ttl: int = 300):
        self._on_spot = on_spot
        self._poll_interval = poll_interval
        self._mode_filter = mode_filter or set()
        self._band_filter = band_filter or set()
        self._running = False
        # Track last-delivered state: call -> (state, timestamp)
        self._last_state = {}
        self._refresh_interval = max(spot_ttl - 30, 60)
        # Summit grid cache: summit_ref -> grid4 (e.g. "W0C/FR-102" -> "DN70")
        self._summit_cache = {}
        self._load_cache()

    def _load_cache(self):
        """Load summit grid cache from disk."""
        try:
            with open(CACHE_FILE, 'r') as f:
                self._summit_cache = json.load(f)
            log.info("[SOTA] Loaded %d cached summit grids from %s",
                     len(self._summit_cache), os.path.basename(CACHE_FILE))
        except (FileNotFoundError, json.JSONDecodeError):
            self._summit_cache = {}

    def _save_cache(self):
        """Save summit grid cache to disk."""
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self._summit_cache, f, indent=2)
        except Exception as e:
            log.warning("[SOTA] Failed to save cache: %s", e)

    def _fetch_spots(self) -> list:
        """Fetch current SOTA spots (blocking HTTP call)."""
        req = urllib.request.Request(
            SOTA_SPOTS_URL,
            headers={'User-Agent': 'GTBridge/1.0', 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def _fetch_summit_grid(self, summit_ref: str) -> Optional[str]:
        """Look up a summit's grid square from the SOTA API (blocking)."""
        # summit_ref format: "W0C/FR-102" -> URL: .../summits/W0C/FR-102
        url = f"{SOTA_SUMMIT_URL}/{summit_ref}"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'GTBridge/1.0', 'Accept': 'application/json'},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                locator = data.get('locator') or ''
                if len(locator) >= 4:
                    return locator[:4]  # 4-char grid for GridTracker
        except Exception as e:
            log.debug("[SOTA] Summit lookup failed for %s: %s", summit_ref, e)
        return None

    async def _get_summit_grid(self, summit_ref: str) -> Optional[str]:
        """Get grid for a summit, using cache or API lookup."""
        if summit_ref in self._summit_cache:
            return self._summit_cache[summit_ref] or None

        grid = await asyncio.to_thread(self._fetch_summit_grid, summit_ref)
        if grid:
            self._summit_cache[summit_ref] = grid
            self._save_cache()
            log.info("[SOTA] Summit %s -> %s", summit_ref, grid)
        else:
            # Cache miss as empty string so we don't retry
            self._summit_cache[summit_ref] = ''
            self._save_cache()
        return grid

    async def _poll(self):
        """Single poll cycle: fetch spots, deliver new ones."""
        try:
            raw_spots = await asyncio.to_thread(self._fetch_spots)
        except Exception as e:
            log.warning("[SOTA] API fetch error: %s", e)
            return

        # The API returns full spot history — keep only the most recent
        # spot per activator callsign (highest spot ID = most recent)
        latest = {}  # call -> spot dict
        for s in raw_spots:
            call = (s.get('activatorCallsign') or '').upper().strip()
            spot_id = s.get('id', 0)
            if not call:
                continue
            if call not in latest or spot_id > latest[call].get('id', 0):
                latest[call] = s

        new_count = 0
        current_calls = set()

        for call, s in latest.items():
            freq_str = s.get('frequency', '0')
            mode = (s.get('mode') or '').upper().strip()
            assoc = s.get('associationCode', '')
            code = s.get('summitCode', '')
            summit_ref = f"{assoc}/{code}"

            if not freq_str:
                continue

            # Skip QRT spots
            comments = (s.get('comments') or '').upper()
            if 'QRT' in comments:
                continue

            # SOTA frequencies are in MHz — convert to kHz
            try:
                freq_mhz = float(freq_str)
            except (ValueError, TypeError):
                continue

            freq_khz = freq_mhz * 1000.0

            # Skip bogus frequencies
            if freq_khz < 1800 or freq_khz > 450000:
                continue

            # Normalize mode
            if mode == 'OTHER':
                mode = ''
            # Skip digital modes — GridTracker handles those natively
            if mode in ('FT8', 'FT4'):
                continue

            current_calls.add(call)

            # Only deliver if new, data changed, or approaching TTL expiry
            now = time.monotonic()
            state = (freq_khz, mode)
            prev = self._last_state.get(call)
            if prev and prev[0] == state and (now - prev[1]) < self._refresh_interval:
                continue

            self._last_state[call] = (state, now)
            new_count += 1

            # Look up summit grid
            grid = await self._get_summit_grid(summit_ref)

            from dxcluster import DXSpot
            spot_time = s.get('timeStamp', '')
            time_utc = spot_time[11:16].replace(':', '') if len(spot_time) >= 16 else '0000'
            spot = DXSpot(
                spotter='SOTA',
                freq_khz=freq_khz,
                dx_call=call,
                comment=summit_ref,
                time_utc=time_utc,
                mode=mode or None,
                snr=None,
                grid=grid,
            )
            spot.activity = 'SOTA'

            await self._on_spot(spot, 'SOTA')

        # Prune activators no longer in the API
        self._last_state = {k: v for k, v in self._last_state.items() if k in current_calls}

        if new_count:
            log.info("[SOTA] %d new/changed activators (%d total active)",
                     new_count, len(current_calls))

    async def run(self):
        """Poll loop — runs until cancelled."""
        self._running = True
        log.info("[SOTA] Polling every %ds from %s", self._poll_interval, SOTA_SPOTS_URL)

        await self._poll()

        while self._running:
            await asyncio.sleep(self._poll_interval)
            await self._poll()

    def stop(self):
        self._running = False
