"""
dxfilter.py — Smart DX Cluster Proxy

Connects to an upstream DX cluster (e.g., VE7CC), filters spots by mode
and time-of-day band relevance, and re-broadcasts filtered spots on a
local telnet port for GTBridge (or any cluster client) to connect to.

Your local skimmer handles FT8/FT4 with real SNR — this tool filters
those out from the upstream cluster and suppresses irrelevant bands
(e.g., 160/80m during the day, 10/12/15m late at night).

Usage:
    python dxfilter.py [--config dxfilter.json]
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse GTBridge modules
import dxcluster
from telnet_server import TelnetServer
from ctydat import CtyDat

log = logging.getLogger('dxfilter')

DEFAULT_CONFIG = {
    "callsign": "WF8Z",
    "grid": "EM79sm",
    "upstream": {
        "host": "dxc.ve7cc.net",
        "port": 23
    },
    "output_port": 7301,
    "cty_dat": "cty.dat",
    "exclude_modes": ["FT8", "FT4"],
    "exclude_continents": [],
    "include_continents": [],
    "day_suppress_bands": ["160m", "80m"],
    "night_suppress_bands": ["6m"],
    "sunrise_utc_hour": 12,
    "sunset_utc_hour": 0,
    "log_level": "INFO"
}


class DXFilter:
    """Smart DX cluster proxy with mode and band filtering."""

    def __init__(self, config: dict):
        self.config = config
        self.callsign = config.get('callsign', 'N0CALL')
        self.exclude_modes = set(
            m.upper() for m in config.get('exclude_modes', [])
        )
        self.exclude_continents = set(
            c.upper() for c in config.get('exclude_continents', [])
        )
        self.include_continents = set(
            c.upper() for c in config.get('include_continents', [])
        )
        self.include_cq_zones = set(config.get('include_cq_zones', []))
        self.exclude_cq_zones = set(config.get('exclude_cq_zones', []))
        self.day_suppress = set(config.get('day_suppress_bands', []))
        self.night_suppress = set(config.get('night_suppress_bands', []))
        self.sunrise_hour = config.get('sunrise_utc_hour', 12)
        self.sunset_hour = config.get('sunset_utc_hour', 0)
        self.region = config.get('region', 2)

        # DXCC lookup
        cty_file = config.get('cty_dat', 'cty.dat')
        try:
            self._cty = CtyDat(cty_file)
            log.info("Loaded cty.dat: %d entities, %d prefixes",
                     self._cty.entity_count, self._cty.prefix_count)
        except FileNotFoundError:
            self._cty = None
            log.warning("cty.dat not found at %s — DXCC lookup disabled", cty_file)

        self._server = None
        self._client = None
        self._spot_count = 0
        self._filtered_count = 0

    def _is_daytime(self) -> bool:
        """Check if it's daytime based on UTC hour."""
        hour = datetime.now(timezone.utc).hour
        if self.sunrise_hour < self.sunset_hour:
            # Normal case: sunrise 12, sunset 23
            return self.sunrise_hour <= hour < self.sunset_hour
        else:
            # Wraps midnight: sunrise 12, sunset 0
            return hour >= self.sunrise_hour or hour < self.sunset_hour

    def _should_filter(self, spot: dxcluster.DXSpot,
                       dx_entity=None, spotter_entity=None) -> str:
        """Check if a spot should be filtered out.

        Returns reason string if filtered, None if spot should pass.
        """
        # Mode filter
        if spot.mode and spot.mode.upper() in self.exclude_modes:
            return f"mode:{spot.mode}"

        # Band/time filter
        band = dxcluster.freq_to_band(spot.freq_khz)
        if band:
            if self._is_daytime() and band in self.day_suppress:
                return f"day:{band}"
            if not self._is_daytime() and band in self.night_suppress:
                return f"night:{band}"

        # Geographic filter on DX station (continent)
        if dx_entity:
            continent = dx_entity.continent.upper()
            if self.include_continents and continent not in self.include_continents:
                return f"continent:{continent}"
            if self.exclude_continents and continent in self.exclude_continents:
                return f"continent:{continent}"

        # Geographic filter on SPOTTER (CQ zone — "can someone near me hear it?")
        if spotter_entity:
            if self.include_cq_zones and spotter_entity.cq_zone not in self.include_cq_zones:
                return f"spotter_zone:{spotter_entity.cq_zone}"
            if self.exclude_cq_zones and spotter_entity.cq_zone in self.exclude_cq_zones:
                return f"spotter_zone:{spotter_entity.cq_zone}"

        return None

    async def _on_spot(self, spot: dxcluster.DXSpot, cluster_name: str):
        """Callback for incoming spots — filter and re-broadcast."""
        self._spot_count += 1

        # Infer mode if not tagged
        if not spot.mode:
            spot.mode = dxcluster.infer_mode(spot.freq_khz, self.region)

        # DXCC lookup for both DX station and spotter
        dx_entity = None
        spotter_entity = None
        if self._cty:
            dx_entity = self._cty.lookup(spot.dx_call)
            # Strip trailing -# from skimmer spotter callsigns
            spotter_call = spot.spotter.rstrip('-#').rstrip('-')
            spotter_entity = self._cty.lookup(spotter_call)

        # Apply filters (dx_entity for continent, spotter_entity for zone)
        reason = self._should_filter(spot, dx_entity, spotter_entity)
        if reason:
            self._filtered_count += 1
            return

        # Re-broadcast to connected clients
        if self._server:
            self._server.broadcast_spot(spot)

        band = dxcluster.freq_to_band(spot.freq_khz) or '?'
        entity_str = f"  [{dx_entity.entity}, {dx_entity.continent}]" if dx_entity else ''
        log.info("[%s] %s  %.1f kHz  %s  [%s]  by %s%s",
                 cluster_name, spot.dx_call, spot.freq_khz,
                 spot.mode or '?', band, spot.spotter, entity_str)

    async def run(self):
        """Start the filter proxy."""
        # Start output telnet server
        output_port = self.config.get('output_port', 7301)
        self._server = TelnetServer(
            host='0.0.0.0',
            port=output_port,
            node_call='DXF-2'
        )
        await self._server.start()

        # Connect to upstream cluster
        upstream = self.config.get('upstream', {})
        login_cmds = upstream.get('login_commands', [])

        self._client = dxcluster.DXClusterClient(
            host=upstream['host'],
            port=upstream.get('port', 23),
            callsign=self.callsign,
            on_spot=self._on_spot,
            name='UPSTREAM',
            login_commands=login_cmds,
        )

        log.info("DXFilter starting")
        log.info("  Upstream: %s:%d", upstream['host'], upstream.get('port', 23))
        log.info("  Output port: %d", output_port)
        log.info("  Exclude modes: %s", ', '.join(self.exclude_modes) or 'none')
        log.info("  Day suppress: %s", ', '.join(self.day_suppress) or 'none')
        log.info("  Night suppress: %s", ', '.join(self.night_suppress) or 'none')
        log.info("  Sunrise: %02d UTC, Sunset: %02d UTC",
                 self.sunrise_hour, self.sunset_hour)
        if self.include_continents:
            log.info("  Include continents: %s", ', '.join(self.include_continents))
        if self.exclude_continents:
            log.info("  Exclude continents: %s", ', '.join(self.exclude_continents))
        if self.include_cq_zones:
            log.info("  Include CQ zones: %s", ', '.join(str(z) for z in self.include_cq_zones))
        if self.exclude_cq_zones:
            log.info("  Exclude CQ zones: %s", ', '.join(str(z) for z in self.exclude_cq_zones))

        # Stats task
        async def print_stats():
            while True:
                await asyncio.sleep(300)
                pct = (self._filtered_count / max(self._spot_count, 1)) * 100
                log.info("Stats: %d spots in, %d filtered (%.0f%%), %d passed",
                         self._spot_count, self._filtered_count, pct,
                         self._spot_count - self._filtered_count)

        stats_task = asyncio.create_task(print_stats())

        try:
            await self._client.connect()
        except asyncio.CancelledError:
            pass
        finally:
            stats_task.cancel()
            self._client.stop()
            await self._server.stop()
            log.info("DXFilter stopped. %d spots processed, %d filtered.",
                     self._spot_count, self._filtered_count)


def main():
    config_path = 'dxfilter.json'
    if len(sys.argv) > 1 and sys.argv[1] == '--config' and len(sys.argv) > 2:
        config_path = sys.argv[2]

    # Load or create config
    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
    else:
        config = DEFAULT_CONFIG
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Created default config: {config_path}")
        print("Edit it and restart.")
        return

    # Setup logging
    level = getattr(logging, config.get('log_level', 'INFO').upper())
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    filt = DXFilter(config)

    try:
        asyncio.run(filt.run())
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == '__main__':
    main()
