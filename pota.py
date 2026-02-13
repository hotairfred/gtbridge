"""
POTA (Parks on the Air) spot fetcher.

Polls the POTA API for active activators and feeds them into the bridge
as DXSpot objects, so they appear in GridTracker's call roster with
"CQ POTA" in the message text.

API endpoint: https://api.pota.app/spot/activator (no auth required)
"""

import asyncio
import json
import logging
import time
import urllib.request
from typing import Callable, Optional

log = logging.getLogger('pota')

POTA_API_URL = 'https://api.pota.app/spot/activator'


class POTAFetcher:
    """Periodically fetches POTA spots and delivers them via callback."""

    def __init__(self, on_spot: Callable, poll_interval: int = 120,
                 mode_filter: Optional[set] = None,
                 band_filter: Optional[set] = None,
                 spot_ttl: int = 300):
        self._on_spot = on_spot
        self._poll_interval = poll_interval
        self._mode_filter = mode_filter or set()
        self._band_filter = band_filter or set()
        # Track last-delivered state: call -> (freq, mode, timestamp)
        # Re-deliver when data changes or before spot_ttl expires
        self._last_state = {}
        self._refresh_interval = max(spot_ttl - 30, 60)  # refresh before TTL
        self._running = False

    def _fetch(self) -> list:
        """Fetch current POTA spots (blocking HTTP call)."""
        req = urllib.request.Request(
            POTA_API_URL,
            headers={'User-Agent': 'GTBridge/1.0', 'Accept': 'application/json'},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))

    async def _poll(self):
        """Single poll cycle: fetch spots, deliver new/changed ones."""
        try:
            spots = await asyncio.to_thread(self._fetch)
        except Exception as e:
            log.warning("[POTA] API fetch error: %s", e)
            return

        new_count = 0
        current_calls = set()

        for s in spots:
            call = (s.get('activator') or '').upper().strip()
            freq_str = s.get('frequency', '0')
            mode = (s.get('mode') or '').upper().strip()
            grid = s.get('grid4') or ''
            reference = s.get('reference') or ''

            if not call or not freq_str:
                continue

            # Skip QRT spots
            comments = (s.get('comments') or '').upper()
            if 'QRT' in comments:
                continue

            try:
                freq_khz = float(freq_str)
            except (ValueError, TypeError):
                continue

            # Skip digital modes — GridTracker handles POTA tagging for FT8/FT4
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

            from dxcluster import DXSpot
            spot_time = s.get('spotTime', '')
            time_utc = spot_time[11:16].replace(':', '') if len(spot_time) >= 16 else '0000'
            spot = DXSpot(
                spotter='POTA',
                freq_khz=freq_khz,
                dx_call=call,
                comment=reference,
                time_utc=time_utc,
                mode=mode or None,
                snr=None,
                grid=grid or None,
            )
            spot.activity = 'POTA'

            await self._on_spot(spot, 'POTA')

        # Prune activators no longer in the API
        self._last_state = {k: v for k, v in self._last_state.items() if k in current_calls}

        if new_count:
            log.info("[POTA] %d new/changed activators (%d total active)",
                     new_count, len(current_calls))

    async def run(self):
        """Poll loop — runs until cancelled."""
        self._running = True
        log.info("[POTA] Polling every %ds from %s", self._poll_interval, POTA_API_URL)

        await self._poll()

        while self._running:
            await asyncio.sleep(self._poll_interval)
            await self._poll()

    def stop(self):
        self._running = False
