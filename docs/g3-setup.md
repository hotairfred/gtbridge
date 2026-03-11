# EliteDesk G3 Skimmer PC Setup

## Hardware
- HP EliteDesk G3 (refurb), Intel i5-7500T (4 cores @ 2.70GHz), 16GB RAM
- IP: 192.168.1.230 (DHCP)
- Login: Skimmer / Skimmer
- NOTE: Original PSU was dead, using G5 Mini PSU
- UEFI mode, Secure Boot disabled, Legacy boot disabled

## TODO
- [ ] Set BIOS "After Power Loss" to "Power On" (needs physical access)
- [ ] Install DXE RF protection / AM broadcast reject filter on pitaya feedline
- [ ] Order replacement G3 PSU or get credit from seller
- [ ] Install Tailscale for tower remote access
- [ ] Set up auto-login + SkimSrv on startup
- [ ] Set up CWSL_DIGI auto-start (after SkimSrv)
- [ ] Set up RBN Aggregator auto-start

## Installed Software
- Windows 11 (debloated with WinUtil `irm christitus.com/win | iex`)
- CW Skimmer Server 1.6.0.145 — `C:\Program Files (x86)\Afreet\SkimSrv`
- CWSL_Tee.dll (2017, 18,432 bytes from CWSL.zip) — in SkimSrv directory
- HermesIntf.dll (v24.1.13) — in SkimSrv directory
- CWSL_DIGI 0.88 — `C:\CWSL_DIGI`
- WSJT-X — `C:\WSJT\wsjtx\bin`
- RBN Aggregator v6.7 — `C:\RBNAggregator`
- Chrome (Edge was broken after debloat)
- Intel Fortran redistributable (libifcoremd.dll for jt9.exe)
- IPP70, VC++ 2010 x86, VC++ 2022 x64 redistributables
- Sysinternals: `C:\Handle\handle64.exe`, `C:\listdlls.exe`

## Completed Setup
- [x] Debloat Windows 11 (WinUtil)
- [x] Enable RDP
- [x] Disable sleep/hibernate/monitor timeout (`powercfg /change *-timeout-ac 0`)
- [x] Disable Windows Update services (registry Start=4)
- [x] Disable Defender real-time scanning
- [x] Remove Skype, bloatware
- [x] Install all skimmer software
- [x] CW skimming working (8 bands, 80-10m)
- [x] FT8 skimming working (CWSL_DIGI via shared memory)
- [x] RBN Aggregator feeding spots to RBN as WF8Z-2
- [x] PSK Reporter enabled
- [x] GTBridge connected to Aggregator port 7550

## Config Files on G3
- `C:\Program Files (x86)\Afreet\SkimSrv\CWSL_Tee.cfg` — `HermesIntf\n8`
- `C:\CWSL_DIGI\config.ini` — active CWSL_DIGI config
- `C:\CWSL_DIGI\config_night.ini` — normal FT8 night bands
- `C:\CWSL_DIGI\config_day.ini` — normal FT8 day bands
- `C:\CWSL_DIGI\config_night_rare.ini` — DXpedition night bands (3567/7090/10131/14090)
- `C:\CWSL_DIGI\config_day_rare.ini` — DXpedition day bands (14090/18095/21090/24911/28090)
- `C:\CWSL_DIGI\switch_mode.bat` — swap configs: `switch_mode.bat night|day|night_rare|day_rare`

## CPU Usage Notes
- SkimSrv alone (CW only, 8 bands): ~15%
- CWSL_DIGI with 2-3 FT8 bands: baseline 22%, spikes to 50% every 15s
- CWSL_DIGI with 4 FT8 bands: spikes to 80%
- 5+ FT8 bands: likely CPU-limited, consider faster hardware
- Watch for Windows Update processes (SetupHost, MRT, svchost/wuauserv) eating CPU
