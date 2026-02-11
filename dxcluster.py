"""
DX Cluster Telnet Client

Connects to DX cluster servers via TCP, logs in with a callsign,
and parses incoming DX spot lines into structured data.

Typical spot format:
  DX de W3LPL:     14074.0  JA1ABC       FT8 -15dB                1234Z
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# Regex to parse standard DX cluster spot lines
# DX de <spotter>:  <freq>  <dx_call>  <comment>  <time>Z
SPOT_RE = re.compile(
    r'^DX\s+de\s+'
    r'(?P<spotter>[A-Z0-9/\-#]+):\s+'
    r'(?P<freq>[\d.]+)\s+'
    r'(?P<dx_call>[A-Z0-9/]+)\s+'
    r'(?P<comment>.*?)\s+'
    r'(?P<time>\d{4})Z\s*$',
    re.IGNORECASE
)

# Try to extract mode from the comment field
MODE_PATTERNS = [
    (re.compile(r'\bFT8\b', re.I), 'FT8'),
    (re.compile(r'\bFT4\b', re.I), 'FT4'),
    (re.compile(r'\bCW\b', re.I), 'CW'),
    (re.compile(r'\bSSB\b', re.I), 'SSB'),
    (re.compile(r'\bRTTY\b', re.I), 'RTTY'),
    (re.compile(r'\bPSK\b', re.I), 'PSK'),
    (re.compile(r'\bJS8\b', re.I), 'JS8'),
    (re.compile(r'\bMSK144\b', re.I), 'MSK144'),
    (re.compile(r'\bJT65\b', re.I), 'JT65'),
    (re.compile(r'\bJT9\b', re.I), 'JT9'),
]

# Try to extract SNR from comment (e.g. "-15 dB" or "-15dB")
SNR_RE = re.compile(r'([+-]?\d{1,3})\s*dB', re.I)

# Try to extract grid square from comment
GRID_RE = re.compile(r'\b([A-R]{2}\d{2}(?:[a-x]{2})?)\b')


@dataclass
class DXSpot:
    """Parsed DX cluster spot."""
    spotter: str
    freq_khz: float
    dx_call: str
    comment: str
    time_utc: str  # "HHMM" format
    mode: Optional[str] = None
    snr: Optional[int] = None
    grid: Optional[str] = None

    @property
    def freq_hz(self) -> int:
        """Frequency in Hz."""
        return int(self.freq_khz * 1000)


def parse_spot(line: str) -> Optional[DXSpot]:
    """Parse a DX cluster spot line. Returns DXSpot or None if not a spot."""
    m = SPOT_RE.match(line.strip())
    if not m:
        return None

    comment = m.group('comment').strip()

    # Extract mode from comment
    mode = None
    for pattern, mode_name in MODE_PATTERNS:
        if pattern.search(comment):
            mode = mode_name
            break

    # Extract SNR from comment
    snr = None
    snr_match = SNR_RE.search(comment)
    if snr_match:
        snr = int(snr_match.group(1))

    # Extract grid from comment
    grid = None
    grid_match = GRID_RE.search(comment)
    if grid_match:
        grid = grid_match.group(1)

    return DXSpot(
        spotter=m.group('spotter').upper(),
        freq_khz=float(m.group('freq')),
        dx_call=m.group('dx_call').upper(),
        comment=comment,
        time_utc=m.group('time'),
        mode=mode,
        snr=snr,
        grid=grid,
    )


def freq_to_band(freq_khz: float) -> Optional[str]:
    """Map frequency in kHz to amateur band name."""
    bands = [
        (1800, 2000, '160m'),
        (3500, 4000, '80m'),
        (5330, 5410, '60m'),
        (7000, 7300, '40m'),
        (10100, 10150, '30m'),
        (14000, 14350, '20m'),
        (18068, 18168, '17m'),
        (21000, 21450, '15m'),
        (24890, 24990, '12m'),
        (28000, 29700, '10m'),
        (50000, 54000, '6m'),
        (144000, 148000, '2m'),
    ]
    for low, high, name in bands:
        if low <= freq_khz <= high:
            return name
    return None


class DXClusterClient:
    """Async TCP client for DX cluster telnet connections."""

    def __init__(self, host: str, port: int, callsign: str,
                 on_spot=None, name: str = None):
        """
        Args:
            host: Cluster server hostname
            port: Cluster server port (typically 7300 or 8000)
            callsign: Your amateur callsign for login
            on_spot: Async callback called with (DXSpot, cluster_name) for each spot
            name: Friendly name for this cluster connection
        """
        self.host = host
        self.port = port
        self.callsign = callsign.upper()
        self.on_spot = on_spot
        self.name = name or f"{host}:{port}"
        self._reader = None
        self._writer = None
        self._running = False

    async def connect(self):
        """Connect to the cluster and begin reading spots."""
        self._running = True
        retry_delay = 5

        while self._running:
            try:
                log.info("[%s] Connecting to %s:%d...", self.name, self.host, self.port)
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=30
                )
                log.info("[%s] Connected.", self.name)
                retry_delay = 5  # reset on successful connect

                await self._login()
                await self._read_loop()

            except asyncio.CancelledError:
                log.info("[%s] Connection cancelled.", self.name)
                break
            except Exception as e:
                log.warning("[%s] Connection error: %s", self.name, e)

            if self._running:
                log.info("[%s] Reconnecting in %ds...", self.name, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 120)

        self._close()

    async def _login(self):
        """Wait for login prompt and send callsign."""
        # Read initial banner/prompt, then send callsign
        # Clusters typically prompt with "login:" or "call:" or "Please enter your call:"
        login_sent = False
        deadline = asyncio.get_event_loop().time() + 15  # 15s timeout for login

        while asyncio.get_event_loop().time() < deadline:
            try:
                data = await asyncio.wait_for(self._reader.read(4096), timeout=5)
            except asyncio.TimeoutError:
                if not login_sent:
                    # Some clusters don't prompt, just send callsign
                    break
                continue

            if not data:
                raise ConnectionError("Connection closed during login")

            text = data.decode('latin-1', errors='replace')
            log.debug("[%s] <<< %s", self.name, text.strip())

            # Check for login prompt
            lower = text.lower()
            if any(kw in lower for kw in ['login', 'call', 'your call', 'enter']):
                self._writer.write((self.callsign + '\r\n').encode())
                await self._writer.drain()
                log.info("[%s] Sent callsign: %s", self.name, self.callsign)
                login_sent = True
                # Read a bit more to clear the post-login banner
                await asyncio.sleep(1)
                return

        # If no prompt was detected, try sending callsign anyway
        if not login_sent:
            self._writer.write((self.callsign + '\r\n').encode())
            await self._writer.drain()
            log.info("[%s] Sent callsign (no prompt detected): %s", self.name, self.callsign)
            await asyncio.sleep(1)

    async def _read_loop(self):
        """Read lines from the cluster and parse spots."""
        buffer = ''
        while self._running:
            try:
                data = await asyncio.wait_for(self._reader.read(4096), timeout=120)
            except asyncio.TimeoutError:
                # Send a keepalive
                try:
                    self._writer.write(b'\r\n')
                    await self._writer.drain()
                except Exception:
                    break
                continue

            if not data:
                log.warning("[%s] Connection closed by server.", self.name)
                break

            buffer += data.decode('latin-1', errors='replace')
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                if not line:
                    continue

                log.debug("[%s] %s", self.name, line)

                # Strip ANSI escape codes (some clusters send color codes)
                clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', line)
                # Strip other control characters
                clean = ''.join(c for c in clean if c >= ' ' or c == '\t')
                clean = clean.strip()

                spot = parse_spot(clean)
                if spot:
                    log.debug("[%s] PARSED: %s on %.1f", self.name, spot.dx_call, spot.freq_khz)
                elif clean.startswith('DX de') or clean.startswith('DX De') or clean.startswith('DX DE'):
                    log.warning("[%s] UNPARSED DX line: %r", self.name, clean)

                if spot and self.on_spot:
                    try:
                        await self.on_spot(spot, self.name)
                    except Exception as e:
                        log.error("[%s] Spot callback error: %s", self.name, e)

    def _close(self):
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
        self._reader = None

    def stop(self):
        """Signal the client to stop."""
        self._running = False
        self._close()
