#!/usr/bin/env python3
"""
gtbridge - DX Cluster to GridTracker 2 Bridge

Connects to one or more DX cluster telnet servers, parses spots, and
sends them to GridTracker 2 as WSJT-X UDP decode messages.

GridTracker sees this as a WSJT-X instance and displays the spots in
its call roster.

Usage:
    python3 gtbridge.py [--config CONFIG_FILE]
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import socket
import sys
import time

import dxcluster
import telnet_server
import wsjtx_udp

log = logging.getLogger('gtbridge')

DEFAULT_CONFIG = {
    "callsign": "WF8Z",
    "grid": "EM79",
    "client_id": "GTB",
    "udp_host": "192.168.1.205",
    "udp_port": 2237,
    "heartbeat_interval": 15,
    "cycle_interval": 15,
    "clusters": [
        {"host": "192.168.1.205", "port": 7373, "name": "SDC"},
    ],
    "spot_ttl": 600,
    "log_level": "INFO",
    "mode_filter": [],
    "band_filter": [],
    "region": 2,
    "telnet_server": False,
    "telnet_port": 7300,
}

# Map modes to WSJT-X decode mode character
MODE_CHAR = {
    'FT8': '~',
    'FT4': '+',
    'JT65': '#',
    'JT9': '@',
    'CW': '~',
    'SSB': '~',
    'RTTY': '~',
    'PSK': '~',
    'JS8': '~',
    'MSK144': '`',
}


class GTBridge:
    """Main bridge: coordinates cluster clients and UDP output.

    Each band+mode combo gets its own WSJT-X client_id (e.g. GTB-20m-CW)
    so GridTracker sees them as separate instances with the correct mode.
    Spots are buffered and flushed every 15 seconds.
    """

    # Default dial frequencies per band (common FT8 frequencies)
    BAND_DIAL_FREQ = {
        '160m': 1840000,
        '80m':  3573000,
        '60m':  5357000,
        '40m':  7074000,
        '30m':  10136000,
        '20m':  14074000,
        '17m':  18100000,
        '15m':  21074000,
        '12m':  24915000,
        '10m':  28074000,
        '6m':   50313000,
        '2m':   144174000,
    }

    def __init__(self, config: dict):
        self.config = config
        self.client_id = config.get('client_id', 'GTBRIDGE')
        self.callsign = config.get('callsign', 'N0CALL')
        self.grid = config.get('grid', '')
        self.udp_host = config.get('udp_host', '127.0.0.1')
        self.udp_port = config.get('udp_port', 2237)
        self.heartbeat_interval = config.get('heartbeat_interval', 15)
        self.cycle_interval = config.get('cycle_interval', 15)
        self.spot_ttl = config.get('spot_ttl', 600)  # seconds to keep re-sending
        self.mode_filter = set(m.upper() for m in config.get('mode_filter', []))
        self.band_filter = set(b.lower() for b in config.get('band_filter', []))
        self.region = config.get('region', 2)
        self._sock = None
        self._telnet = None
        self._cluster_clients = []
        self._spot_count = 0
        self._send_count = 0  # total UDP decode packets sent (including resends)
        # Spot cache: keyed by (band, dx_call) -> {spot, cluster_name, first_seen, last_updated}
        self._spot_cache = {}
        self._cache_lock = asyncio.Lock()
        # Track which (band, mode) combos we've seen (for heartbeats)
        self._active_instances = set()

    def _instance_client_id(self, band: str, mode: str) -> str:
        """Return the WSJT-X client_id for a band+mode instance."""
        return f"{band}-{mode}"

    def _send_udp(self, data: bytes):
        """Send a UDP packet to GridTracker."""
        try:
            self._sock.sendto(data, (self.udp_host, self.udp_port))
        except Exception as e:
            log.error("UDP send error: %s", e)

    async def _on_spot(self, spot: dxcluster.DXSpot, cluster_name: str):
        """Callback when a DX spot is received — adds/updates cache."""
        # Infer mode from frequency band plan if not tagged
        if not spot.mode:
            spot.mode = dxcluster.infer_mode(spot.freq_khz, self.region)

        # Apply mode filter
        if self.mode_filter and (not spot.mode or spot.mode.upper() not in self.mode_filter):
            log.info("[%s] Filtered: %s  %.1f kHz  mode=%s",
                     cluster_name, spot.dx_call, spot.freq_khz, spot.mode or 'None')
            return

        band = dxcluster.freq_to_band(spot.freq_khz)
        if not band:
            log.debug("Skipping spot on unknown band: %.1f kHz", spot.freq_khz)
            return

        # Apply band filter
        if self.band_filter and band.lower() not in self.band_filter:
            return

        now = time.time()
        key = (band, spot.dx_call)

        async with self._cache_lock:
            if key in self._spot_cache:
                # Update existing spot (refreshes data, keeps original first_seen)
                self._spot_cache[key]['spot'] = spot
                self._spot_cache[key]['cluster_name'] = cluster_name
                self._spot_cache[key]['last_updated'] = now
                log.info("[%s] Updated: %s  %.1f kHz  %s  [%s]  by %s",
                         cluster_name, spot.dx_call, spot.freq_khz, spot.mode or '??', band, spot.spotter)
            else:
                # New spot
                self._spot_cache[key] = {
                    'spot': spot,
                    'cluster_name': cluster_name,
                    'first_seen': now,
                    'last_updated': now,
                }
                self._spot_count += 1
                log.info("[%s] New: %s  %.1f kHz  %s  [%s]  by %s",
                         cluster_name, spot.dx_call, spot.freq_khz, spot.mode or '??', band, spot.spotter)

            # Broadcast to telnet clients in real time
            if self._telnet:
                self._telnet.broadcast_spot(spot)

            # Register this band+mode (sends initial heartbeat+status on first spot)
            inst = (band, spot.mode)
            if inst not in self._active_instances:
                self._active_instances.add(inst)
                cid = self._instance_client_id(band, spot.mode)
                dial = self.BAND_DIAL_FREQ.get(band, spot.freq_hz)
                self._send_udp(wsjtx_udp.heartbeat(client_id=cid))
                self._send_udp(wsjtx_udp.status(
                    client_id=cid, dial_freq=dial, mode=spot.mode,
                    de_call=self.callsign, de_grid=self.grid, decoding=True,
                ))
                log.info("New instance: %s (dial=%d Hz)", cid, dial)

    async def _flush_cycle(self):
        """Send all cached (non-expired) spots to GridTracker.

        Every cycle re-sends all spots still within the TTL so they
        stay visible in GridTracker's call roster.  Expired spots are
        removed from the cache.
        """
        now = time.time()

        # Expire old spots and group active ones by (band, mode)
        by_inst = {}  # (band, mode) -> list of (spot, cluster_name)
        expired_keys = []

        async with self._cache_lock:
            for key, entry in self._spot_cache.items():
                age = now - entry['last_updated']
                if age > self.spot_ttl:
                    expired_keys.append(key)
                else:
                    spot = entry['spot']
                    inst = (key[0], spot.mode or 'SSB')
                    if inst not in by_inst:
                        by_inst[inst] = []
                    by_inst[inst].append((spot, entry['cluster_name']))

            for key in expired_keys:
                del self._spot_cache[key]

        if expired_keys:
            log.debug("Expired %d spots from cache", len(expired_keys))

        time_ms = wsjtx_udp.current_time_ms()
        total_sent = 0

        for (band, mode), spots in by_inst.items():
            cid = self._instance_client_id(band, mode)
            dial = self.BAND_DIAL_FREQ.get(band, spots[0][0].freq_hz)

            # Send Status for this band+mode instance
            self._send_udp(wsjtx_udp.status(
                client_id=cid, dial_freq=dial, mode=mode,
                de_call=self.callsign, de_grid=self.grid, decoding=True,
            ))

            # Re-send all cached decodes for this instance
            for spot, cluster_name in spots:
                if spot.grid:
                    msg_text = f"CQ {spot.dx_call} {spot.grid}"
                else:
                    msg_text = f"CQ {spot.dx_call}"

                snr = spot.snr if spot.snr is not None else -10
                mode_char = MODE_CHAR.get(spot.mode, '~') if spot.mode else '~'
                audio_freq = 200 + (hash(spot.dx_call) % 2800)

                self._send_udp(wsjtx_udp.decode(
                    client_id=cid, is_new=True, time_ms=time_ms,
                    snr=snr, delta_time=0.0, delta_freq=audio_freq,
                    mode=mode_char, message=msg_text,
                    low_confidence=False, off_air=False,
                ))
                total_sent += 1

        self._send_count += total_sent
        if total_sent:
            log.info("Cycle: sent %d spots across %d instances (%d cached, %d expired)",
                     total_sent, len(by_inst),
                     sum(len(s) for s in by_inst.values()), len(expired_keys))

    async def _cycle_loop(self):
        """Every 15 seconds, flush buffered spots to GridTracker."""
        while True:
            await asyncio.sleep(self.cycle_interval)
            await self._flush_cycle()

    async def _heartbeat_loop(self):
        """Send periodic heartbeat for every active band+mode instance."""
        while True:
            for band, mode in list(self._active_instances):
                cid = self._instance_client_id(band, mode)
                self._send_udp(wsjtx_udp.heartbeat(client_id=cid))
            log.debug("Heartbeats sent for %d instances (spots: %d)",
                      len(self._active_instances), self._spot_count)
            await asyncio.sleep(self.heartbeat_interval)

    async def _stats_loop(self):
        """Log periodic stats."""
        while True:
            await asyncio.sleep(60)
            instances = ', '.join(f"{b}-{m}" for b, m in sorted(self._active_instances))
            log.info("Stats: %d unique spots, %d in cache, %d sends, instances: %s",
                     self._spot_count, len(self._spot_cache),
                     self._send_count, instances)

    async def run(self):
        """Main entry point - run the bridge."""
        # Create UDP socket
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        log.info("UDP target: %s:%d (client_id=%s)",
                 self.udp_host, self.udp_port, self.client_id)
        log.info("Callsign: %s  Grid: %s", self.callsign, self.grid or '(not set)')

        log.info("Spot TTL: %d seconds (%d minutes)", self.spot_ttl, self.spot_ttl // 60)

        if self.mode_filter:
            log.info("Mode filter: %s", ', '.join(self.mode_filter))
        if self.band_filter:
            log.info("Band filter: %s", ', '.join(self.band_filter))

        # Start telnet server if enabled
        if self.config.get('telnet_server', False):
            port = self.config.get('telnet_port', 7300)
            node_call = self.callsign + '-2'
            self._telnet = telnet_server.TelnetServer(
                host='0.0.0.0', port=port, node_call=node_call)
            await self._telnet.start()

        # Band instances are created dynamically as spots arrive.
        # No initial heartbeat needed — each band sends its own on first spot.

        # Build tasks
        tasks = []

        # Heartbeat + cycle + stats loops
        tasks.append(asyncio.create_task(self._heartbeat_loop()))
        tasks.append(asyncio.create_task(self._cycle_loop()))
        tasks.append(asyncio.create_task(self._stats_loop()))

        # Cluster clients
        clusters = self.config.get('clusters', [])
        if not clusters:
            log.error("No clusters configured!")
            return

        for cluster_cfg in clusters:
            client = dxcluster.DXClusterClient(
                host=cluster_cfg['host'],
                port=cluster_cfg.get('port', 7300),
                callsign=self.callsign,
                on_spot=self._on_spot,
                name=cluster_cfg.get('name', cluster_cfg['host']),
                login_commands=cluster_cfg.get('login_commands', []),
            )
            self._cluster_clients.append(client)
            tasks.append(asyncio.create_task(client.connect()))
            log.info("Cluster: %s (%s:%d)",
                     client.name, cluster_cfg['host'], cluster_cfg.get('port', 7300))

        log.info("Bridge running. Press Ctrl+C to stop.")

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for client in self._cluster_clients:
                client.stop()
            if self._telnet:
                await self._telnet.stop()
            if self._sock:
                self._sock.close()
            log.info("Bridge stopped. Total spots forwarded: %d", self._spot_count)


def load_config(config_path: str) -> dict:
    """Load config from JSON file, falling back to defaults."""
    config = dict(DEFAULT_CONFIG)

    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                user_config = json.load(f)
            config.update(user_config)
            log.info("Loaded config from %s", config_path)
        except Exception as e:
            log.error("Error loading config %s: %s", config_path, e)
    else:
        # Write default config for the user to edit
        try:
            with open(config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            log.info("Created default config at %s - please edit it with your callsign!", config_path)
        except Exception as e:
            log.warning("Could not write default config: %s", e)

    return config


def main():
    parser = argparse.ArgumentParser(
        description='DX Cluster to GridTracker 2 Bridge',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example config (gtbridge.json):
{
  "callsign": "W1AW",
  "grid": "FN31",
  "udp_host": "127.0.0.1",
  "udp_port": 2237,
  "clusters": [
    {"host": "dxc.nc7j.com", "port": 7300, "name": "NC7J"}
  ],
  "mode_filter": [],
  "band_filter": []
}

Filters:
  mode_filter: [] = all modes, or ["FT8", "CW"] etc.
  band_filter: [] = all bands, or ["20m", "40m"] etc.
        """
    )
    parser.add_argument('--config', '-c', default='gtbridge.json',
                        help='Config file path (default: gtbridge.json)')
    parser.add_argument('--log-level', '-l', default=None,
                        help='Log level (DEBUG, INFO, WARNING, ERROR)')
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Set up logging
    level = args.log_level or config.get('log_level', 'INFO')
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    if config.get('callsign', 'N0CALL') == 'N0CALL':
        log.warning("=" * 60)
        log.warning("  Callsign is N0CALL - edit %s with your callsign!", args.config)
        log.warning("=" * 60)

    bridge = GTBridge(config)

    # Handle Ctrl+C gracefully
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown(sig, frame):
        log.info("Shutting down...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(bridge.run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == '__main__':
    main()
