# Red Pitaya CW + FT8 Skimmer Setup

## Overview
CW Skimmer Server + CWSL_Tee + CWSL_DIGI decoding CW and FT8/FT4 simultaneously from a single Red Pitaya STEMlab 125-14. RBN Aggregator combines all spots and feeds them to RBN, PSK Reporter, and GTBridge.

## Hardware
- **Red Pitaya STEMlab 125-14** — IP: 192.168.1.54, MAC: 00:26:32:F0:98:04
- Pavel Demin Alpine image (20251012), `sdr_receiver_hpsdr` app, 8 DDC receivers
- Noctua NF-A4x10 5V fan on 2-pin header (label side up = blow down onto board)
- Baseline temp: 42°C with fan, 8 bands, March basement
- **EliteDesk G3** — IP: 192.168.1.230, Login: Skimmer/Skimmer, Windows 11 debloated
- CPU: Intel i5-7500T (4 cores @ 2.70GHz), 16GB RAM

## Software Stack
| Component | Version | Purpose | Source |
|-----------|---------|---------|--------|
| CW Skimmer Server | 1.6.0.145 | CW decoding | dxatlas.com (licensed) |
| HermesIntf DLL | v24.1.13 | HPSDR protocol bridge | [k3it/HermesIntf](https://github.com/k3it/HermesIntf/releases) — **use v24.1.13+** |
| CWSL_Tee | 2017 (18,432 bytes) | IQ shared memory splitter | [HrochL/CWSL](https://github.com/HrochL/CWSL) — **CWSL.zip, NOT GoodOldStable** |
| CWSL_DIGI | 0.88 | FT8/FT4 decoder | [alexranaldi/CWSL_DIGI](https://github.com/alexranaldi/CWSL_DIGI) |
| WSJT-X | — | Provides jt9.exe decoder | wsjt.sourceforge.io |
| RBN Aggregator | v6.7 | Combines CW+FT8, feeds RBN/PSK Reporter | reversebeacon.net |

## Prerequisites (manual downloads)
1. **HermesIntf DLL** — https://github.com/k3it/HermesIntf/releases
   - Copy as `HermesIntf.dll` in SkimSrv directory
   - Also keep a copy as `HermesIntf_192.168.1.54.dll` on the share
   - **Version matters** — v18.5.22 does NOT work. Use v24.1.13+
2. **CWSL_Tee.dll** — https://github.com/HrochL/CWSL → `bin/CWSL.zip`
   - **CRITICAL: Use the 2017 version (18,432 bytes) from CWSL.zip**
   - The 2014 GoodOldStable version (17,408 bytes) does NOT create shared memory
   - Place in SkimSrv directory
3. **Intel Fortran redistributable** — https://drive.google.com/drive/folders/1pk99ruANXTd_87oLce2L32H2V-P6dAFn
   - Provides `libifcoremd.dll` needed by jt9.exe
4. **WSJT-X** — install to `C:\WSJT\wsjtx\bin`
5. **CW Skimmer Server** — install and license (installs to `C:\Program Files (x86)\Afreet\SkimSrv`)
6. **RBN Aggregator** — download from reversebeacon.net, install to `C:\RBNAggregator`

## Automated Setup
Run `setup_skimmer.bat` as Administrator from the share (`\\192.168.1.101\motorola\`).

It installs:
- IPP70 (Intel Primitives) DLLs to `C:\Windows\SysWOW64`
- VC++ 2010 x86 redistributable
- VC++ 2022 x64 redistributable
- CWSL_Tee.dll + config into SkimSrv directory
- CWSL_DIGI to `C:\CWSL_DIGI` with config.ini

## CWSL_Tee.cfg
Located in SkimSrv directory (`C:\Program Files (x86)\Afreet\SkimSrv`). Two lines:
```
HermesIntf
8
```
- Line 1: underlying SDR DLL name (no `.dll` extension). Use `HermesIntf` (short name), NOT `HermesIntf_192.168.1.54`
- Line 2: circular buffer depth in blocks (default 64, 8 also works). This is NOT the number of receivers — it's how many IQ blocks the ring buffer holds.

**Shared memory naming**: derived from the CWSL_Tee DLL filename. `CWSL_Tee.dll` creates `CWSL0Band` through `CWSL7Band`. If you rename the DLL (e.g. `CWSL_Tee1.dll`), the names change accordingly.

## Red Pitaya Startup
```bash
ssh root@192.168.1.54  # password: changeme
cd /root && ./start.sh
```
start.sh runs `sdr_receiver_hpsdr` with 8 receivers.

## SkimSrv Configuration
1. Start SkimSrv
2. Skimmer tab → select **"CWSL_Tee on 9804"**
3. Set SegmentBandwidth to **192 kHz**
4. Configure 8 bands: 80/40/30/20/17/15/12/10m
5. SkimSrv cluster telnet: port **7300** (used by Aggregator internally)

## CWSL_DIGI Configuration
Config file: `C:\CWSL_DIGI\config.ini`

Key settings:
```ini
[radio]
sharedmem=-1         # -1 for single receiver setup

[operator]
callsign=WF8Z
gridsquare=EM79sm

[decoders]
decoder=14074000 FT8
decoder=7074000 FT8

[wsjtx]
temppath=C:\CWSL_DIGI\wave
binpath=C:\WSJT\wsjtx\bin

[reporting]
pskreporter=true
rbn=true
aggregatorport=2215
```

### Band switching configs
Multiple configs on `C:\CWSL_DIGI\` for different scenarios:
- `config_night.ini` — Normal FT8: 80/40/20m (3573, 7074, 14074)
- `config_day.ini` — Normal FT8: 20/17/15/12/10m (14074, 18100, 21074, 24915, 28074)
- `config_night_rare.ini` — Bouvet/DXpedition: 80/40/30/20m (3567, 7090, 10131, 14090)
- `config_day_rare.ini` — Bouvet/DXpedition: 20/17/15/12/10m (14090, 18095, 21090, 24911, 28090)

Switch with: `C:\CWSL_DIGI\switch_mode.bat night|day|night_rare|day_rare`

### CPU considerations
Each FT8 band spawns jt9.exe every 15 seconds. On a 4-core i5-7500T:
- 2-3 bands: comfortable (spikes to 50%)
- 4 bands: manageable (spikes to 80%)
- 5+ bands: CPU-limited, may miss decode cycles
- A faster PC would allow all 8 bands simultaneously

## RBN Aggregator Configuration
- Install to `C:\RBNAggregator`
- Callsign: WF8Z
- CWSL_DIGI input port: **2215** (must be enabled in Aggregator GUI)
- Local user telnet port: **7550** (DX cluster format output)
- Feeds spots to RBN as WF8Z-2

## Data Flow
```
Red Pitaya (IQ) → SkimSrv → CWSL_Tee → shared memory → CWSL_DIGI (FT8)
                      ↓                                       ↓
                  CW spots                               FT8 spots
                      ↓                                       ↓
                  Aggregator ←────────────────────────────────┘
                      ↓              (port 2215)
                 port 7550
                 (combined)
                      ↓
                  GTBridge → GridTracker (UDP)
                      ↓
                 RBN + PSK Reporter
```

## Running
1. Start Red Pitaya (`./start.sh` via SSH)
2. Start SkimSrv (CW decoding begins)
3. Start RBN Aggregator
4. Start CWSL_DIGI: `C:\CWSL_DIGI\switch_mode.bat night` (or day/night_rare/day_rare)
5. GTBridge connects to Aggregator on port 7550

## Windows Optimization (dedicated skimmer box)
```powershell
# Disable sleep/hibernate
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 0

# Disable Windows Update (registry, survives reboots)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\UsoSvc" -Name "Start" -Value 4
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\wuauserv" -Name "Start" -Value 4

# Disable Defender real-time scanning
Set-MpPreference -DisableRealtimeMonitoring $true
```

## Troubleshooting
- **"timed out waiting on UDP data"** — Wrong HermesIntf DLL version. Use v24.1.13+
- **"Unable to open CWSL shared memory"** — Wrong CWSL_Tee.dll version. Must use 2017 version (18,432 bytes) from CWSL.zip. The 2014 GoodOldStable (17,408 bytes) does NOT create shared memory with SkimSrv 1.6.x.
- **CWSL_DIGI can't find libifcoremd.dll** — Install Intel Fortran redistributable from Google Drive link above
- **SkimSrv shows "CWSL_Tee without low..."** — CWSL_Tee can't load the underlying DLL. Check that CWSL_Tee.cfg line 1 matches the DLL name exactly (without .dll extension) and the DLL exists in the SkimSrv directory.
- **No FT8 spots in GTBridge** — Verify: (1) CWSL_DIGI has `rbn=true` and `aggregatorport=2215`, (2) Aggregator has port 2215 enabled for CWSL_DIGI input, (3) GTBridge connects to Aggregator port 7550 (not SkimSrv 7300)
- **Verify shared memory**: `handle64.exe -accepteula -p SkimSrv.exe | findstr CWSL` — should show `CWSL0Band` through `CWSL7Band`
- **Verify DLL loading**: `listdlls.exe -accepteula SkimSrv.exe | findstr /i CWSL` — should show CWSL_Tee.dll loaded
- **tasklist /m doesn't show DLLs** — Normal for 32-bit WoW64 processes. Use Sysinternals `listdlls.exe` instead.
- **High CPU** — Check for Windows Update processes: `Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU`. Kill SetupHost, MRT. Disable wuauserv/UsoSvc.
- **SkimSrv won't stop cleanly** — `Stop-Process -Name SkimSrv -Force` (may show two processes, kill both)

## Diagnostic Tools (on G3)
- `C:\Handle\handle64.exe` — Sysinternals handle viewer (shared memory verification)
- `C:\listdlls.exe` — Sysinternals DLL lister (32-bit DLL verification)

## Monitoring
- **CPU temp on pitaya:** `cat /sys/bus/iio/devices/iio:device0/in_temp0_raw` — formula: `(offset + raw) * scale / 1000`
- **GTBridge skimmer spots:** `tail -f gtbridge.log | grep WF8Z-2`
- **CWSL_DIGI debug:** set `loglevel=8` in config.ini
- **RBN leaderboard:** W3RGA top spotter page (resets 00:30 UTC daily)
- **PSK Reporter:** pskreporter.info — search for reporter WF8Z

## Network Notes
- Red Pitaya streams IQ over gigabit ethernet (no bandwidth issues)
- SkimSrv cluster on port 7300 feeds Aggregator locally
- Aggregator combines CW+FT8, serves on port 7550 (DX cluster telnet format)
- GTBridge connects to Aggregator port 7550 (not SkimSrv 7300 directly)
- At tower site: Tailscale direct connection, no public cluster relay needed
