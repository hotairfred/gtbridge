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
import base64
import json
import logging
import os
import signal
import socket
import sys
import time

import xml.etree.ElementTree as ET

import dxcluster
import flexradio
import pota
import qrz
import sota
import telnet_server
import wsjtx_udp

log = logging.getLogger('gtbridge')

DEFAULT_CONFIG = {
    "callsign": "N0CALL",
    "grid": "",
    "client_id": "GTB",
    "udp_host": "127.0.0.1",
    "udp_port": 2237,
    "heartbeat_interval": 15,
    "cycle_interval": 15,
    "clusters": [
        {"host": "dxc.nc7j.com", "port": 7373, "name": "cluster"},
    ],
    "spot_ttl": 600,
    "log_level": "INFO",
    "mode_filter": [],
    "band_filter": [],
    "region": 2,
    "telnet_server": False,
    "telnet_port": 7300,
    "log_file": "",
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

    # Band lower edge frequencies (Hz) — used as dial_freq base so that
    # dial + delta_freq = actual spotted frequency in GridTracker.
    BAND_DIAL_FREQ = {
        '160m': 1800000,
        '80m':  3500000,
        '60m':  5330000,
        '40m':  7000000,
        '30m':  10100000,
        '20m':  14000000,
        '17m':  18068000,
        '15m':  21000000,
        '12m':  24890000,
        '10m':  28000000,
        '6m':   50000000,
        '2m':   144000000,
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
        self.qrz_skimmer_only = config.get('qrz_skimmer_only', False)
        self._sock = None
        self._telnet = None
        self._qrz = None
        self._flex = None
        self._pota = None
        self._sota = None
        self._n1mm_sock = None
        self._cluster_clients = []
        self._spot_count = 0
        self._send_count = 0  # total UDP decode packets sent (including resends)
        # Spot cache: keyed by (band, dx_call) -> {spot, cluster_name, first_seen, last_updated}
        self._spot_cache = {}
        # Stale cache: expired spots kept for click-to-tune (5 min grace period)
        self._stale_cache = {}
        self._stale_ttl = 300  # 5 minutes
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

        # QRZ grid lookup (skip SOTA — summit grids come from SOTA API)
        if self._qrz and getattr(spot, 'activity', None) != 'SOTA':
            if spot.grid:
                # Source provided a grid — update cache (authoritative)
                self._qrz.update_cache(spot.dx_call, spot.grid)
            elif (not self.qrz_skimmer_only
                  or '#' in (spot.spotter or '')
                  or getattr(spot, 'activity', None)):
                # Always look up grids for POTA spots
                grid = await self._qrz.lookup_grid(spot.dx_call)
                if grid:
                    spot.grid = grid

        now = time.time()
        key = (band, spot.dx_call)

        async with self._cache_lock:
            if key in self._spot_cache:
                old_spot = self._spot_cache[key]['spot']
                # Sticky activity tag — once tagged POTA/SOTA, keep it
                if not getattr(spot, 'activity', None) and getattr(old_spot, 'activity', None):
                    spot.activity = old_spot.activity
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
                entry = self._spot_cache.pop(key)
                entry['expired_at'] = now
                self._stale_cache[key] = entry

            # Purge stale entries past the grace period
            stale_expired = [k for k, v in self._stale_cache.items()
                             if now - v['expired_at'] > self._stale_ttl]
            for key in stale_expired:
                del self._stale_cache[key]

        if expired_keys:
            log.debug("Expired %d spots from cache (%d stale)",
                      len(expired_keys), len(self._stale_cache))

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
                activity = getattr(spot, 'activity', None)
                cq_prefix = f"CQ {activity}" if activity else "CQ"
                if spot.grid:
                    msg_text = f"{cq_prefix} {spot.dx_call} {spot.grid[:4]}"
                else:
                    msg_text = f"{cq_prefix} {spot.dx_call}"

                snr = spot.snr if spot.snr is not None else -10
                mode_char = MODE_CHAR.get(spot.mode, '~') if spot.mode else '~'
                audio_freq = spot.freq_hz

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

    async def _udp_listener(self):
        """Listen for Reply messages from GridTracker on the sending socket."""
        loop = asyncio.get_event_loop()
        while True:
            try:
                data = await loop.sock_recv(self._sock, 4096)
                if data:
                    self._handle_reply(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("UDP recv error: %s", e)

    def _handle_reply(self, data: bytes):
        """Handle a Reply message (type 4) from GridTracker."""
        reply = wsjtx_udp.parse_reply(data)
        if reply is None:
            return

        # Parse the clicked callsign from the message
        # Formats: "CQ CALL [GRID]" or "CQ POTA CALL [GRID]" or "CQ SOTA CALL [GRID]"
        parts = (reply.get('message') or '').split()
        if len(parts) < 2:
            return
        if len(parts) >= 3 and parts[1] in ('POTA', 'SOTA'):
            dx_call = parts[2]
        else:
            dx_call = parts[1]
        client_id = reply.get('client_id', '')

        # Determine band and mode from the client_id (e.g. "40m-CW")
        if '-' not in client_id:
            return
        band, mode = client_id.rsplit('-', 1)

        if not self._flex or not self._flex.connected:
            log.debug("[Flex] Reply for %s but Flex not connected", dx_call)
            return

        # Find the spot in cache (or stale cache) to get the exact frequency
        key = (band, dx_call)
        entry = self._spot_cache.get(key) or self._stale_cache.get(key)
        if not entry:
            log.info("[Flex] %s clicked but not in cache", dx_call)
            return
        spot = entry['spot']
        freq_mhz = spot.freq_khz / 1000.0

        # Dedicated slice: tune and change mode directly
        dedicated = self.config.get('flex_slice')
        if dedicated is not None:
            log.info("[Flex] %s clicked: tuning slice %d to %.3f kHz %s (%s)",
                     dx_call, dedicated, spot.freq_khz, mode, band)
            asyncio.create_task(self._flex.tune_to_spot(dedicated, freq_mhz, mode))
            return

        # No dedicated slice: find a matching one by band+mode
        sn = self._flex.find_slice(band, mode)
        if sn is None:
            log.info("[Flex] %s clicked: no %s %s slice available", dx_call, band, mode)
            return

        log.info("[Flex] %s clicked: tuning slice %d to %.3f kHz (%s %s)",
                 dx_call, sn, spot.freq_khz, band, mode)
        asyncio.create_task(self._flex.tune(sn, freq_mhz))

    # ------------------------------------------------------------------ #
    #  N1MM / SDC-Connectors QSO logging                                   #
    # ------------------------------------------------------------------ #

    async def _n1mm_listener(self):
        """Listen for N1MM-compatible QSO broadcasts from SDC-Connectors."""
        loop = asyncio.get_event_loop()
        while True:
            try:
                data = await loop.sock_recv(self._n1mm_sock, 8192)
                if data:
                    self._handle_n1mm(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("N1MM recv error: %s", e)

    def _handle_n1mm(self, data: bytes):
        """Handle an N1MM-compatible UDP broadcast."""
        try:
            text = data.decode('utf-8', errors='replace')
            root = ET.fromstring(text)
        except ET.ParseError:
            return

        if root.tag == 'contactinfo':
            self._handle_n1mm_contact(root)

    def _handle_n1mm_contact(self, root):
        """Handle a contactinfo (QSO logged) message from SDC-Connectors."""
        dx_call = root.findtext('call', '')
        if not dx_call:
            return

        mode = root.findtext('mode', '').upper()
        # N1MM/SDC frequencies are in 10 Hz units
        rx_freq_raw = int(root.findtext('rxfreq', '0'))
        freq_hz = rx_freq_raw * 10
        freq_khz = freq_hz / 1000.0

        grid = root.findtext('gridsquare', '')
        report_sent = root.findtext('snt', '')
        report_rcvd = root.findtext('rcv', '')
        my_call = root.findtext('mycall', '') or self.callsign
        exchange_sent = root.findtext('sntnr', '')
        exchange_rcvd = root.findtext('rcvnr', '')

        # Parse timestamp "2026-02-14 17:58:20"
        dt_off = None
        timestamp = root.findtext('timestamp', '')
        if timestamp:
            try:
                dp, tp = timestamp.split()
                yy, mm, dd = dp.split('-')
                hh, mi, ss = tp.split(':')
                dt_off = (int(yy), int(mm), int(dd),
                          int(hh), int(mi), int(ss))
            except (ValueError, IndexError):
                pass

        band = dxcluster.freq_to_band(freq_khz)
        if not band:
            log.warning("[N1MM] Unknown band for %.1f kHz", freq_khz)
            return

        # Ensure band+mode instance exists in GridTracker
        cid = self._instance_client_id(band, mode)
        inst = (band, mode)
        if inst not in self._active_instances:
            self._active_instances.add(inst)
            dial = self.BAND_DIAL_FREQ.get(band, freq_hz)
            self._send_udp(wsjtx_udp.heartbeat(client_id=cid))
            self._send_udp(wsjtx_udp.status(
                client_id=cid, dial_freq=dial, mode=mode,
                de_call=self.callsign, de_grid=self.grid, decoding=True,
            ))
            log.info("New instance: %s (dial=%d Hz)", cid, dial)

        # Send QSO Logged to GridTracker
        self._send_udp(wsjtx_udp.qso_logged(
            client_id=cid,
            dx_call=dx_call,
            dx_grid=grid[:4] if grid else '',
            freq_hz=freq_hz,
            mode=mode,
            report_sent=report_sent,
            report_rcvd=report_rcvd,
            my_call=my_call,
            my_grid=self.grid,
            date_time_off=dt_off,
            exchange_sent=exchange_sent,
            exchange_rcvd=exchange_rcvd,
        ))

        log.info("[N1MM] QSO logged: %s  %.1f kHz  %s  [%s]",
                 dx_call, freq_khz, mode, band)

    async def run(self):
        """Main entry point - run the bridge."""
        # Create UDP socket (non-blocking for async recv in _udp_listener)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
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

        # QRZ grid lookups
        qrz_user, qrz_pass = _load_secrets(self.config)
        if qrz_user and qrz_pass:
            self._qrz = qrz.QRZLookup(qrz_user, qrz_pass)
            log.info("QRZ XML lookup enabled for %s", qrz_user)

        # FlexRadio integration
        if self.config.get('flex_radio', False):
            flex_host = self.config.get('flex_host', '127.0.0.1')
            flex_port = self.config.get('flex_port', 4992)
            self._flex = flexradio.FlexRadioClient(flex_host, flex_port)
            log.info("Flex Radio: %s:%d", flex_host, flex_port)

        # POTA spots
        if self.config.get('pota_spots', False):
            poll_interval = self.config.get('pota_poll_interval', 120)
            self._pota = pota.POTAFetcher(
                on_spot=self._on_spot,
                poll_interval=poll_interval,
                mode_filter=self.mode_filter,
                band_filter=self.band_filter,
                spot_ttl=self.spot_ttl,
            )
            log.info("POTA spots enabled (polling every %ds)", poll_interval)

        # SOTA spots
        if self.config.get('sota_spots', False):
            poll_interval = self.config.get('sota_poll_interval', 120)
            self._sota = sota.SOTAFetcher(
                on_spot=self._on_spot,
                poll_interval=poll_interval,
                mode_filter=self.mode_filter,
                band_filter=self.band_filter,
                spot_ttl=self.spot_ttl,
            )
            log.info("SOTA spots enabled (polling every %ds)", poll_interval)

        # N1MM-compatible QSO logging (SDC-Connectors)
        if self.config.get('n1mm_listen', False):
            n1mm_port = self.config.get('n1mm_port', 12060)
            self._n1mm_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._n1mm_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._n1mm_sock.bind(('', n1mm_port))
            self._n1mm_sock.setblocking(False)
            log.info("N1MM listener: UDP port %d", n1mm_port)

        # Band instances are created dynamically as spots arrive.
        # No initial heartbeat needed — each band sends its own on first spot.

        # Build tasks
        tasks = []

        # Heartbeat + cycle + stats loops
        tasks.append(asyncio.create_task(self._heartbeat_loop()))
        tasks.append(asyncio.create_task(self._cycle_loop()))
        tasks.append(asyncio.create_task(self._stats_loop()))

        # Flex Radio client
        if self._flex:
            tasks.append(asyncio.create_task(self._flex.run()))
            tasks.append(asyncio.create_task(self._udp_listener()))

        # POTA fetcher
        if self._pota:
            tasks.append(asyncio.create_task(self._pota.run()))

        # SOTA fetcher
        if self._sota:
            tasks.append(asyncio.create_task(self._sota.run()))

        # N1MM listener
        if self._n1mm_sock:
            tasks.append(asyncio.create_task(self._n1mm_listener()))

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
            if self._pota:
                self._pota.stop()
            if self._sota:
                self._sota.stop()
            if self._flex:
                self._flex.stop()
            if self._telnet:
                await self._telnet.stop()
            if self._n1mm_sock:
                self._n1mm_sock.close()
            if self._sock:
                self._sock.close()
            log.info("Bridge stopped. Total spots forwarded: %d", self._spot_count)


def _decode_password(value: str) -> str:
    """Decode a password that may be base64-obfuscated (b64: prefix)."""
    if value.startswith('b64:'):
        return base64.b64decode(value[4:]).decode('utf-8')
    return value


def _load_secrets(config: dict) -> tuple:
    """Load QRZ credentials from secrets.json or environment variables."""
    user = os.environ.get('QRZ_USER', '')
    password = os.environ.get('QRZ_PASSWORD', '')
    if user and password:
        return user, password

    secrets_file = config.get('secrets_file', 'secrets.json')
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file) as f:
                secrets = json.load(f)
            user = secrets.get('qrz_user', '')
            password = _decode_password(secrets.get('qrz_password', ''))
        except Exception as e:
            log.warning("Could not load secrets from %s: %s", secrets_file, e)

    return user, password


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
    log_fmt = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    log_datefmt = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_fmt,
        datefmt=log_datefmt,
    )

    # Optional file logging
    log_file = config.get('log_file', '')
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(getattr(logging, level.upper(), logging.INFO))
        fh.setFormatter(logging.Formatter(log_fmt, datefmt=log_datefmt))
        logging.getLogger().addHandler(fh)
        logging.getLogger('gtbridge').info("Logging to file: %s", log_file)

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
