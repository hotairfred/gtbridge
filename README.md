# GTBridge - DX Cluster to GridTracker 2 Bridge

GTBridge connects to DX cluster telnet servers (including SDC-Connectors) and feeds spots into GridTracker 2's call roster by emulating WSJT-X UDP messages.

If you use GridTracker 2 and want to see DX cluster spots in the call roster without running WSJT-X, this is for you.

## Features

- Connects to one or more DX cluster servers via telnet
- Parses standard DX cluster spot format (including SDC-Connectors)
- Creates a separate WSJT-X instance per band (e.g. GTB-20m, GTB-40m) so GridTracker can track spots on multiple bands simultaneously
- Caches spots and re-sends them every 15 seconds so they persist in GridTracker's call roster for a configurable duration (default 10 minutes)
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

4. In GridTracker 2, you should see spots appearing in the call roster. Each band shows up as a separate instance (GTB-20m, GTB-40m, etc.) in the General tab.

## Configuration

Edit `gtbridge.json`:

```json
{
  "callsign": "W1AW",
  "grid": "FN31",
  "client_id": "GTB",
  "udp_host": "192.168.1.205",
  "udp_port": 2237,
  "heartbeat_interval": 15,
  "cycle_interval": 15,
  "spot_ttl": 600,
  "clusters": [
    {"host": "192.168.1.205", "port": 7373, "name": "SDC"}
  ],
  "log_level": "INFO",
  "mode_filter": [],
  "band_filter": [],
  "telnet_server": true,
  "telnet_port": 7300
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `callsign` | Your amateur radio callsign (used for cluster login) | `N0CALL` |
| `grid` | Your Maidenhead grid square (4 or 6 char) | `""` |
| `client_id` | Prefix for WSJT-X instance names in GridTracker | `GTB` |
| `udp_host` | IP address of the machine running GridTracker 2 | `127.0.0.1` |
| `udp_port` | UDP port GridTracker is listening on | `2237` |
| `heartbeat_interval` | Seconds between heartbeat messages | `15` |
| `cycle_interval` | Seconds between spot send cycles | `15` |
| `spot_ttl` | Seconds to keep re-sending a spot before it expires | `600` (10 min) |
| `clusters` | List of DX cluster servers to connect to | See below |
| `log_level` | Logging verbosity: DEBUG, INFO, WARNING, ERROR | `INFO` |
| `mode_filter` | Only forward these modes (empty = all) | `[]` |
| `band_filter` | Only forward these bands (empty = all) | `[]` |
| `telnet_server` | Enable built-in telnet server for HRD/loggers | `false` |
| `telnet_port` | TCP port for the telnet server | `7300` |

### Cluster Server Config

Each entry in `clusters` needs:
- `host` — hostname or IP address
- `port` — TCP port number
- `name` — friendly name (shown in logs)

### Filter Examples

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
3. Parses incoming DX spot lines (callsign, frequency, mode, SNR)
4. Groups spots by band — each band gets its own WSJT-X "instance"
5. Every 15 seconds, sends all cached spots as WSJT-X Decode messages via UDP
6. GridTracker 2 receives these and displays them in the call roster
7. Spots are re-sent each cycle until they age out (default 10 minutes)
8. If the telnet server is enabled, each spot is also broadcast in real time to connected clients (HRD, Log4OM, etc.)

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
