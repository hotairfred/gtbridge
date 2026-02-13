# GTBridge - DX Cluster to GridTracker 2 Bridge

GTBridge connects to DX cluster telnet servers (including SDC-Connectors) and feeds spots into GridTracker 2's call roster by emulating WSJT-X UDP messages.

If you use GridTracker 2 and want to see DX cluster spots in the call roster without running WSJT-X, this is for you.

## Features

- Connects to one or more DX cluster servers via telnet
- Parses standard DX cluster spot format (including SDC-Connectors)
- Infers mode (CW/SSB/FT8/FT4) from frequency when the cluster doesn't provide one, using ITU region band plans and standard digital dial frequencies
- Creates a separate WSJT-X instance per band and mode (e.g. 20m-CW, 40m-SSB) so GridTracker displays the correct mode for each spot
- Caches spots and re-sends them every 15 seconds so they persist in GridTracker's call roster for a configurable duration (default 10 minutes)
- Re-spots reset the TTL — active stations stay visible as long as they keep getting spotted
- Sends `sh/dx` on connect to pre-fill the cache with recent spots
- Supports per-cluster login commands for server-side filtering
- POTA (Parks on the Air) spots — polls the POTA API for active activators and displays them in the call roster with grids and bearings (no subscription required)
- QRZ XML grid lookups — automatically populates grid squares for spotted callsigns (requires QRZ XML subscription)
- FlexRadio click-to-tune — clicking a spot in GridTracker's call roster tunes a matching Flex 6000 series slice to that frequency
- Built-in telnet server re-broadcasts spots to Ham Radio Deluxe, Log4OM, or any DX cluster client (emulates DX Spider node with VE7CC CC11 support)
- Filters by mode and/or band
- Pure Python 3 — no external dependencies

## Requirements

- Python 3.8 or later
- GridTracker 2 listening on UDP port 2237

## Quick Start

1. Download the Python files into the same directory:
   - `gtbridge.py`
   - `dxcluster.py`
   - `wsjtx_udp.py`
   - `telnet_server.py`
   - `pota.py` (optional — only needed for POTA spots)
   - `qrz.py` (optional — only needed for QRZ grid lookups)
   - `flexradio.py` (optional — only needed for FlexRadio click-to-tune)

2. Run it:
   ```
   python3 gtbridge.py
   ```

3. On the first run, a `gtbridge.json` config file is created. Edit it with your callsign and settings, then run again.

4. In GridTracker 2, you should see spots appearing in the call roster. Each band+mode combo shows up as a separate instance (20m-CW, 40m-SSB, etc.) in the General tab.

## Configuration

Edit `gtbridge.json`:

```json
{
  "callsign": "W1AW",
  "grid": "FN31",
  "udp_host": "127.0.0.1",
  "udp_port": 2237,
  "heartbeat_interval": 15,
  "cycle_interval": 15,
  "spot_ttl": 600,
  "region": 2,
  "clusters": [
    {
      "host": "dxc.nc7j.com",
      "port": 7373,
      "name": "cluster",
      "login_commands": []
    }
  ],
  "log_level": "INFO",
  "mode_filter": ["CW", "SSB"],
  "band_filter": [],
  "telnet_server": true,
  "telnet_port": 7300,
  "qrz_skimmer_only": false
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `callsign` | Your amateur radio callsign (used for cluster login) | `N0CALL` |
| `grid` | Your Maidenhead grid square (4 or 6 char) | `""` |
| `udp_host` | IP address of the machine running GridTracker 2 | `127.0.0.1` |
| `udp_port` | UDP port GridTracker is listening on | `2237` |
| `heartbeat_interval` | Seconds between heartbeat messages | `15` |
| `cycle_interval` | Seconds between spot send cycles | `15` |
| `spot_ttl` | Seconds to keep re-sending a spot (resets on re-spot) | `600` (10 min) |
| `region` | ITU region for band plan mode inference (1, 2, or 3) | `2` |
| `clusters` | List of DX cluster servers to connect to | See below |
| `log_level` | Logging verbosity: DEBUG, INFO, WARNING, ERROR | `INFO` |
| `mode_filter` | Only forward these modes (empty = all) | `[]` |
| `band_filter` | Only forward these bands (empty = all) | `[]` |
| `telnet_server` | Enable built-in telnet server for HRD/loggers | `false` |
| `telnet_port` | TCP port for the telnet server | `7300` |
| `qrz_skimmer_only` | Only do QRZ grid lookups for skimmer-decoded spots | `false` |
| `pota_spots` | Enable POTA activator spots from pota.app | `false` |
| `pota_poll_interval` | Seconds between POTA API polls | `120` |
| `sota_spots` | Enable SOTA activator spots from sota.org.uk | `false` |
| `sota_poll_interval` | Seconds between SOTA API polls | `120` |
| `flex_radio` | Enable FlexRadio click-to-tune integration | `false` |
| `flex_host` | IP address of the FlexRadio | `127.0.0.1` |
| `flex_port` | SmartSDR TCP API port | `4992` |
| `flex_slice` | Dedicated slice for click-to-tune (0-7), unset = auto-match | not set |

### ITU Regions

The `region` setting controls which band plan is used for mode inference:

| Region | Coverage |
|--------|----------|
| 1 | Europe, Africa, Middle East |
| 2 | Americas (ARRL band plan) |
| 3 | Asia-Pacific |

### Cluster Server Config

Each entry in `clusters` supports:
- `host` — hostname or IP address
- `port` — TCP port number
- `name` — friendly name (shown in logs)
- `login_commands` — (optional) list of commands sent after login, before `sh/dx`

#### Login Commands

Use `login_commands` to send server-side filter commands to the cluster after login. This reduces bandwidth by having the cluster drop unwanted spots before sending them. The exact syntax depends on the cluster software (DX Spider, AR-Cluster, etc.).

DX Spider examples:
```json
"login_commands": [
    "reject/spot on hf/ft8",
    "reject/spot on hf/ft4",
    "set/nobeacon"
]
```

Commands are sent in order with a short pause between each. The `sh/dx` command is always sent last to pre-fill the spot cache.

### Mode Inference

When a DX cluster spot arrives without a mode tag, GTBridge infers the mode from the frequency:

1. **FT4/FT8 detection** — checks if the frequency falls within 3 kHz of a standard FT4 or FT8 dial frequency (e.g. 14074 kHz for 20m FT8, 7047.5 kHz for 40m FT4)
2. **Band plan lookup** — checks ITU region band plan for CW and SSB sub-bands (e.g. 14000-14070 kHz is CW in Region 2)
3. **Gray area default** — frequencies between CW and SSB sub-bands (e.g. 7070-7125 kHz on 40m) default to SSB, since the operator can identify the actual mode on their radio

If the cluster spot already includes a mode tag (e.g. "CW" or "FT8" in the comment), that mode is used as-is.

### Filter Examples

Only CW and SSB spots (filters out FT8, FT4, RTTY, etc.):
```json
"mode_filter": ["CW", "SSB"]
```

Only FT8 and CW spots:
```json
"mode_filter": ["FT8", "CW"]
```

Only 20m and 40m:
```json
"band_filter": ["20m", "40m"]
```

## Common DX Cluster Servers

| Server | Port | Notes |
|--------|------|-------|
| dxc.nc7j.com | 7300 | NC7J DXSpider cluster |
| Your SDC-Connectors | 7373 | Local, includes skimmer spots |

## Running on Different Platforms

### Linux / Mac

```bash
python3 gtbridge.py
```

Or with a custom config:
```bash
python3 gtbridge.py --config /path/to/myconfig.json
```

To run with verbose logging:
```bash
python3 gtbridge.py -l DEBUG
```

### Windows

1. Install Python 3.8+ from https://www.python.org/downloads/
   - During install, check "Add Python to PATH"
2. Download the four `.py` files into a folder
3. Open Command Prompt or PowerShell, navigate to the folder, and run:
   ```
   python gtbridge.py
   ```
4. Edit `gtbridge.json` with your settings and run again.

### Running as a Service on Ubuntu / Debian

This sets GTBridge up to start automatically at boot and restart if it crashes.

1. Copy the GTBridge files somewhere permanent:
   ```bash
   sudo mkdir -p /opt/gtbridge
   sudo cp gtbridge.py dxcluster.py wsjtx_udp.py telnet_server.py pota.py qrz.py flexradio.py gtbridge.json /opt/gtbridge/
   ```

2. Create a system user (optional, runs the service without a login shell):
   ```bash
   sudo useradd -r -s /usr/sbin/nologin gtbridge
   sudo chown -R gtbridge:gtbridge /opt/gtbridge
   ```

3. Create the service file `/etc/systemd/system/gtbridge.service`:
   ```ini
   [Unit]
   Description=GTBridge - DX Cluster to GridTracker Bridge
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=gtbridge
   WorkingDirectory=/opt/gtbridge
   ExecStart=/usr/bin/python3 /opt/gtbridge/gtbridge.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

4. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable gtbridge
   sudo systemctl start gtbridge
   ```

5. Check status and logs:
   ```bash
   sudo systemctl status gtbridge
   sudo journalctl -u gtbridge -f
   ```

To update GTBridge later, copy the new files to `/opt/gtbridge/` and run:
```bash
sudo systemctl restart gtbridge
```

#### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: "When the computer starts"
4. Action: Start a Program
   - Program: `python`
   - Arguments: `gtbridge.py`
   - Start in: `C:\path\to\gtbridge`

## Ham Radio Deluxe (HRD) Setup

GTBridge includes a built-in telnet server that emulates a DX Spider cluster node. HRD (or any DX cluster client) can connect directly and receive live spots.

1. Enable the telnet server in `gtbridge.json`:
   ```json
   "telnet_server": true,
   "telnet_port": 7300
   ```

2. In HRD, add a new DX cluster connection:
   - **Host:** the IP address of the machine running GTBridge
   - **Port:** 7300 (or whatever you set `telnet_port` to)
   - **Type:** DX Spider

3. Connect — spots should appear in HRD's spot window as they arrive.

The server identifies itself as `YOURCALL-2` (e.g. `WF8Z-2`) and supports HRD's VE7CC CC11 spot format, which HRD enables automatically via `set/ve7cc`. See `HRD_TELNET_PROTOCOL.txt` for detailed protocol notes.

## QRZ Grid Lookups

GTBridge can look up grid squares for spotted callsigns via the QRZ.com XML API. This populates the grid field in GridTracker's call roster, so you can see where stations are located and get azimuth bearings. Requires a QRZ XML Logbook Data subscription.

### Setup

1. Create a `secrets.json` file in the same directory as `gtbridge.py`:
   ```json
   {
     "qrz_user": "your_callsign",
     "qrz_password": "your_qrz_password"
   }
   ```

2. That's it — GTBridge will detect the credentials and enable QRZ lookups automatically. You'll see `QRZ XML lookup enabled` in the log.

### Password Obfuscation

If you'd rather not store the password in plain text, you can base64-encode it:

```bash
echo -n 'your_password' | base64
```

Then use the `b64:` prefix in `secrets.json`:
```json
{
  "qrz_user": "your_callsign",
  "qrz_password": "b64:eW91cl9wYXNzd29yZA=="
}
```

You can also use environment variables instead of `secrets.json`:
```bash
export QRZ_USER=your_callsign
export QRZ_PASSWORD=your_password
python3 gtbridge.py
```

### Skimmer-Only Mode

By default, QRZ lookups are performed for all spotted callsigns. If you're running a local CW skimmer (e.g. SDC-Connectors), you can limit lookups to only skimmer-decoded spots:

```json
"qrz_skimmer_only": true
```

This matches GridTracker's philosophy of "show what you can hear" — skimmer spots mean the station was decoded locally, so the grid is meaningful. Spots from human spotters on the cluster are passed through without a QRZ lookup (they'll still show in the roster, just without a grid or bearing).

Set `qrz_skimmer_only` to `false` (the default) if you're using a regular DX cluster without a local skimmer and want grids for all spots.

### Bearings

GridTracker calculates azimuth bearings automatically from your grid to each spotted station's grid. As long as the spot has a grid (either from the cluster or from a QRZ lookup), the Azim column in the call roster will be populated. No additional configuration is needed — just make sure your `grid` is set correctly in `gtbridge.json`.

### How It Works

- When a new callsign is spotted, GTBridge checks its local cache first
- On a cache miss, it queries the QRZ XML API for the grid square
- Results are cached to disk (`qrz_cache.json`) to avoid redundant lookups
- If a cluster spot already includes a grid, that grid is used as-is and saved to the cache
- Lookups are rate-limited (2 seconds between API calls) to avoid hammering the QRZ server
- Transient failures (network errors, session timeouts) are not cached — the callsign will be retried on the next spot

### Notes

- `secrets.json` and `qrz_cache.json` are excluded from git via `.gitignore`
- The grid is truncated to 4 characters in the WSJT-X decode message to match the FT8 message format that GridTracker expects
- The QRZ module uses only Python stdlib (`urllib.request`) — no additional dependencies

## POTA (Parks on the Air) Spots

GTBridge can pull active POTA activator spots from the pota.app API and display them in GridTracker's call roster. This is useful for POTA chasers who want to see park activators alongside DX cluster spots — especially on CW and SSB, where GridTracker doesn't automatically detect POTA activity.

### Setup

Add this to `gtbridge.json`:

```json
"pota_spots": true
```

That's it. No account or API key needed — the POTA API is public.

### How It Works

- GTBridge polls the POTA activator spot feed every 2 minutes (configurable via `pota_poll_interval`)
- FT8/FT4 spots are skipped since GridTracker already handles POTA tagging for digital modes
- CW and SSB activators are sent to GridTracker as decode messages with `CQ POTA CALL GRID` in the message text
- Grids come directly from the POTA API — no QRZ lookup needed
- Spots go through the same mode and band filters as cluster spots
- POTA spots are also broadcast to telnet clients (HRD, Log4OM, etc.) if the telnet server is enabled

## FlexRadio Click-to-Tune

If you have a FlexRadio 6000 series radio, GTBridge can tune it when you click a spot in GridTracker's call roster. It connects to the radio via the SmartSDR TCP API (port 4992), monitors which slices are active, and tunes the matching slice to the spotted frequency.

### Setup

Add these settings to `gtbridge.json`:

```json
{
  "flex_radio": true,
  "flex_host": "your.flex.ip.address",
  "flex_port": 4992,
  "flex_slice": 1
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `flex_radio` | Enable FlexRadio integration | `false` |
| `flex_host` | IP address of the FlexRadio | `your.flex.ip.address` |
| `flex_port` | SmartSDR TCP API port | `4992` |
| `flex_slice` | Dedicated slice number for click-to-tune (0-7) | not set |

### How It Works

1. GTBridge connects to the radio and subscribes to slice status updates
2. It tracks all active slices — their frequency, band, and mode
3. When you click a callsign in GridTracker's call roster, GridTracker sends a Reply message back via UDP
4. GTBridge parses the reply to identify the clicked callsign, band, and mode
5. It tunes the dedicated slice (if `flex_slice` is set) or finds a matching slice by band and mode
6. The slice is tuned to the exact spotted frequency and its mode is changed to match the spot

### Dedicated Slice Mode

When `flex_slice` is set, all click-to-tune actions go to that one slice. The slice's mode is automatically changed to match the spot (CW spots set CW mode, SSB spots set USB/LSB, RTTY spots set DIGU). This is ideal for contest operating — your run slice stays untouched while the dedicated S&P slice follows your clicks across bands and modes.

If `flex_slice` is not set, GTBridge falls back to finding an existing slice that matches the spot's band and mode. In this mode, it only tunes — it never changes the slice's mode.

### Behavior

- **Auto-reconnect** — if the radio connection drops, it reconnects automatically
- **Mode mapping** — CW→CW, SSB→USB/LSB (by frequency), RTTY→RTTY, FT8/FT4→DIGU

## How It Works

```
                                                  GridTracker 2
                                                  (UDP decode + reply)
                                                       ^  |
                                                       |  v
DX Cluster(s) --telnet--> dxcluster.py --spots--> gtbridge.py
POTA API ----http poll--> pota.py ------spots-->/  |    |      |
                                            qrz.py  flex     telnet_server.py
                                         (grid lkp) radio.py (DX Spider node)
                                                     |            ^
                                                     v            |
                                                  FlexRadio   HRD / loggers
                                                  (tune)      (telnet)
```

1. Connects to configured DX cluster server(s) via TCP telnet
2. Logs in with your callsign
3. Sends any configured `login_commands` (server-side filters, etc.)
4. Sends `sh/dx` to get recent spots and pre-fill the cache
5. Parses incoming DX spot lines (callsign, frequency, mode, SNR, grid, spotter)
6. Infers mode from frequency when not provided by the cluster
7. Groups spots by band and mode — each combo gets its own WSJT-X "instance" (e.g. 20m-CW, 40m-SSB)
8. Every 15 seconds, sends all cached spots as WSJT-X Decode messages via UDP
9. GridTracker 2 receives these and displays them in the call roster with the correct mode
10. Spots are re-sent each cycle until they age out (default 10 minutes); re-spots reset the timer
11. If the telnet server is enabled, each spot is also broadcast in real time to connected clients (HRD, Log4OM, etc.)

## Troubleshooting

**GridTracker doesn't show anything:**
- Make sure `udp_host` points to the machine running GridTracker
- Check that GridTracker is listening on port 2237 (General tab)
- If GridTracker is on a different machine, ensure no firewall blocks UDP 2237
- Try running with `-l DEBUG` to see if spots are being parsed

**No spots from cluster:**
- Verify the cluster host/port are correct
- Check your callsign is set (clusters require valid callsign login)
- Run with `-l DEBUG` to see raw cluster data

**Spots appear but don't persist:**
- Increase `spot_ttl` in config (default 600 seconds)
- Check GridTracker's call roster age-out setting

**Spots show wrong mode:**
- Check `region` is set correctly for your location (1=Europe, 2=Americas, 3=Asia-Pacific)
- Mode inference only applies when the cluster doesn't tag the spot — if the cluster says "CW", that's used as-is

**HRD connects but spot window is empty:**
- Make sure `telnet_server` is `true` in gtbridge.json
- In HRD, set the cluster type to "DX Spider"
- HRD requires VE7CC CC11 format — GTBridge handles this automatically when HRD sends `set/ve7cc`
- Check that HRD is connecting to the right IP and port (default 7300)
- See `HRD_TELNET_PROTOCOL.txt` for detailed protocol notes

## SDC-Connectors Notes

GTBridge works with SDC-Connectors' built-in telnet DX cluster server. SDC aggregates spots from its CW/RTTY/BPSK skimmers plus external DX cluster sources, so you may only need to connect to SDC rather than multiple internet clusters.

See `SDC_TELNET_ISSUES.txt` for known compatibility notes about SDC's telnet server.

## License

MIT License. Do whatever you want with it — just keep the copyright notice. See [LICENSE](LICENSE) for details. 73!
