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
  "udp_host": "192.168.1.205",
  "udp_port": 2237,
  "heartbeat_interval": 15,
  "cycle_interval": 15,
  "spot_ttl": 600,
  "region": 2,
  "clusters": [
    {
      "host": "192.168.1.205",
      "port": 7373,
      "name": "SDC",
      "login_commands": []
    }
  ],
  "log_level": "INFO",
  "mode_filter": ["CW", "SSB"],
  "band_filter": [],
  "telnet_server": true,
  "telnet_port": 7300
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
   sudo cp gtbridge.py dxcluster.py wsjtx_udp.py telnet_server.py gtbridge.json /opt/gtbridge/
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

## How It Works

```
                                                  GridTracker 2
                                                  (UDP decode msgs)
                                                       ^
                                                       |
DX Cluster(s) --telnet--> dxcluster.py --spots--> gtbridge.py
                                                       |
                                                       v
                                                  telnet_server.py
                                                  (DX Spider emulator)
                                                       ^
                                                       |
                                                  HRD / loggers
                                                  (telnet clients)
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
