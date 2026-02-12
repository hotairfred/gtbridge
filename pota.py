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
import urllib.request
from typing import Callable, Optional

log = logging.getLogger('pota')

POTA_API_URL = 'https://api.pota.app/spot/activator'


class POTAFetcher:
    """Periodically fetches POTA spots and delivers them via callback."""

    def __init__(self, on_spot: Callable, poll_interval: int = 120,
                 mode_filter: Optional[set] = None,
                 band_filter: Optional[set] = None):
        """
        Args:
            on_spot: async callback(spot, source_name) — same signature as cluster spots
            poll_interval: seconds between API polls (default 120)
            mode_filter: set of modes to include (empty/None = all)
            band_filter: set of bands to include (empty/None = all)
        """
        self._on_spot = on_spot
        self._poll_interval = poll_interval
        self._mode_filter = mode_filter or set()
        self._band_filter = band_filter or set()
        self._seen = {}  # spotId -> True, to avoid re-processing same spot
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
        """Single poll cycle: fetch spots, deliver new ones."""
        try:
            spots = await asyncio.to_thread(self._fetch)
        except Exception as e:
            log.warning("[POTA] API fetch error: %s", e)
            return

        new_count = 0
        current_ids = set()

        for s in spots:
            spot_id = s.get('spotId')
            if spot_id is None:
                continue
            current_ids.add(spot_id)

            # Skip if we already processed this exact spot
            if spot_id in self._seen:
                continue

            call = (s.get('activator') or '').upper().strip()
            freq_str = s.get('frequency', '0')
            mode = (s.get('mode') or '').upper().strip()
            grid = s.get('grid4') or ''
            reference = s.get('reference') or ''

            if not call or not freq_str:
                continue

            try:
                freq_khz = float(freq_str)
            except (ValueError, TypeError):
                continue

            # Skip digital modes — GridTracker handles POTA tagging for FT8/FT4
            if mode in ('FT8', 'FT4'):
                continue

            self._seen[spot_id] = True
            new_count += 1

            # Build a DXSpot-compatible object
            from dxcluster import DXSpot
            # Extract HHMM from spotTime (e.g. "2026-02-12T23:08:46")
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
            # Tag as POTA so flush_cycle can use "CQ POTA" message format
            spot.pota = True
            spot.pota_ref = reference

            await self._on_spot(spot, 'POTA')

        # Prune seen IDs that are no longer in the API response
        self._seen = {k: v for k, v in self._seen.items() if k in current_ids}

        if new_count:
            log.info("[POTA] %d new activators (%d total active)", new_count, len(spots))

    async def run(self):
        """Poll loop — runs until cancelled."""
        self._running = True
        log.info("[POTA] Polling every %ds from %s", self._poll_interval, POTA_API_URL)

        # Initial fetch immediately
        await self._poll()

        while self._running:
            await asyncio.sleep(self._poll_interval)
            await self._poll()

    def stop(self):
        self._running = False
