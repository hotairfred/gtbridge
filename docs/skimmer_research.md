# Skimmer Research Notes

Research into turning a Hermes Lite 2 into a multi-band CW/digi skimmer,
with focus on GTBridge integration. March 2026.

## The Goal

Use a spare HL2 as a dedicated receive-only skimmer that decodes CW and
FT8/FT4 across all HF bands simultaneously, feeding spots into GridTracker
via GTBridge — either directly or through RBN.

## Fred's HL2 Setup

- **IP:** 192.168.1.46 (DHCP — consider static lease on Mikrotik)
- **Board version:** hl2b5up (2nd iteration board, confirmed)
- **10-RX gateware file:** `hl2b5up_cicrx.rbf`
- **Flash tool:** SparkSDR (has firmware upload built in — no need for Quisk/Python)
- **Thetis** also connects and works, but close it before using SparkSDR or SkimSrv
- **No web interface** — HL2 speaks HPSDR over UDP only, won't show on port 80 scans
- **No TX** on 10-RX gateware — flash back to `hl2b5up_main.rbf` to restore TX
- **Antenna:** SDR Switch (sdrswitch.com) shares Flex antenna, or DXE-RG5000HD RF limiter as alternative
- **SkimSrv license key:** `000014-0BC3E3-U8GYQX-R10M0H-JKQG1C-KJWDKY-NMAK66-YU86XF-C6JQFV-8EBRDZ` (also unlocks CW Skimmer Server — same key)

## HL2 as a Skimmer Platform

The Hermes Lite 2 is an open-source HF SDR transceiver based on a broadband
modem chip and the HPSDR Hermes project. Key skimmer-relevant specs:

- **Standard gateware:** 4 RX slices + TX
- **10-RX gateware variant:** Swaps TX logic for extra receivers, giving
  10 simultaneous RX slices with no transmit. This is the skimmer firmware.
- **Protocol:** HPSDR over UDP (same as original Hermes/Angelia/Orion)
- **Bandwidth:** 192 kHz per slice at max sample rate
- **Cost:** ~$300 assembled from Makerfabs

With 10 slices at 192 kHz each, you can cover all major HF bands simultaneously.
People running this setup report **20,000+ spots/day**.

Gateware files: `https://github.com/softerhardware/Hermes-Lite2/tree/master/gateware/bitfiles`
The RX-only variant is at: `stable/<version>/variants/hl2b5up_cicrx/hl2b5up_cicrx.rbf`

## Windows Software Stack (Proven, Production)

This is the established approach used by RBN node operators. All Windows-only.

### CW Skimmer Server (SkimSrv) — by Afreet Software (VE3NEA)

- Commercial software, ~$75, 30-day trial
- http://www.dxatlas.com/cwskimmer/
- Multi-channel CW decoder with adaptive speed detection
- Weak-signal performance is genuinely hard to replicate (the "secret sauce")
- Built-in telnet server on port 7300 — outputs standard DX cluster format spots
- Needs a hardware interface DLL to talk to the SDR

### HermesIntf DLL — by K3IT

- `https://github.com/k3it/HermesIntf`
- Plugin DLL that bridges HPSDR protocol to SkimSrv
- Supports Hermes, Hermes Lite, Red Pitaya, Angelia, Griffin, Metis
- HL2 gets 8 receivers through this DLL (not all 10 — protocol limitation?)
- **KV4TT fork recommended** (`https://github.com/KV4TT/HermesIntf`) — better
  watchdog timer handling, fixes connection drops
- Can be renamed to lock to a specific SDR IP: `HermesIntf_192.168.1.xxx.dll`
  (critical when Flex 6700 is on same network — otherwise it may try to
  talk to the Flex instead of the HL2)

### CWSL — by HrochL

- `https://github.com/HrochL/CWSL`
- Shared memory bridge between SkimSrv and CWSL_DIGI
- `CWSL_Tee.dll` goes in the SkimSrv folder, loads automatically
- Makes receiver audio available via Windows shared memory

### CWSL_DIGI v0.88 — by N2ADR (Alex Ranaldi)

- `https://github.com/alexranaldi/CWSL_DIGI`
- Decodes FT8, FT4, JT65, WSPR, FST4, FST4W, JS8
- Uses jt9 binary from WSJT-X installation for actual decoding
- Taps into SkimSrv's audio via CWSL shared memory
- Reports spots to PSK Reporter, RBN (via Aggregator port 2215), WSPRNet
- Config file (`config.ini`) defines decoder lines: `decoder=14074000 FT8`
- Requires MS Visual Studio 2022 C++ Redist and Intel Fortran Redist
- Must be installed outside of Program Files (Windows permissions)
- Run from command prompt to see error output

### RBN Aggregator

- Consolidates CW spots from SkimSrv telnet and FT spots from CWSL_DIGI
- Forwards everything to the Reverse Beacon Network
- FT# tab: source 40, port 2215 for CWSL_DIGI spots
- Only needed if contributing spots to RBN (not needed for local use)

### Frequency Calibration Note

HL2 oscillator drifts. SkimSrv and CWSL_DIGI need reciprocal calibration
values. If SkimSrv FreqCalibration = 0.999998765, CWSL_DIGI needs 1.000001235.
Calibrate before going live on RBN/PSK Reporter — bad cal spreads wrong
frequencies to the whole network.

## Linux-Native Alternatives (Explored, Limited)

The original question was whether this could be done without Windows.
Short answer: digi modes yes, CW no.

### DigiSkimmer (Python, Linux)

- `https://github.com/lazywalker/DigiSkimmer`
- Python-based FT8/FT4 skimmer, calls jt9 directly
- Originally built for KiwiSDR but decoding pipeline is SDR-agnostic
- Could potentially be adapted for HL2 via SoapySDR
- Reports to PSK Reporter
- Inspiration from wsprdaemon project
- Claims 10,000+ spots/24hr from single KiwiSDR with 10 band requests

### JvanKatwijk/cwskimmer (C++, Linux, GPL-2.0)

- `https://github.com/JvanKatwijk/cwskimmer`
- Linux CW skimmer — the only open-source option found
- Very limited: only 48 frequency bins at ~100 Hz spacing = ~4 kHz coverage
- Computes spectrum 500 times/second
- More proof-of-concept than production. Not comparable to SkimSrv.
- Would need massive expansion to cover full band widths

### fldigi Bayesian CW Decoder

- fldigi has an experimental multi-channel CW decoder
- Auto-detects CW signals in audio band, spins up decoder per signal
- Runs on Linux, could potentially run headless
- Still single-audio-stream, not wideband SDR-native
- Development status unclear — was in alpha builds

### RSCW

- `https://www.pa3fwm.nl/software/rscw/`
- Linux CW decoder using soundcard
- Single-channel only, must specify WPM manually
- Machine-sent CW only (perfect timing)
- Not useful for skimming

### SoapySDR + SoapyHermesLite

- Could provide a standard Linux SDR API to pull IQ from HL2
- Would be the "front end" for any Linux skimmer pipeline
- The missing piece is a good CW decoder backend

### Theoretical Linux Pipeline

```
HL2 (10-RX gateware)
  → SoapySDR / raw HPSDR UDP
    → jt9 for FT8/FT4 (works today)
    → ??? for CW (nothing production-ready)
      → local spots → GTBridge → GridTracker
```

**Bottom line:** Nobody has built a credible open-source Linux wideband CW
skimmer that competes with VE3NEA's SkimSrv. The adaptive speed detection
and weak-signal algorithm is genuinely hard to replicate. Linux can handle
the digi modes fine via jt9, but CW skimming currently requires the Windows
stack.

## GTBridge Integration Options

### Direct Telnet to SkimSrv (Simplest)

SkimSrv's built-in telnet server on port 7300 speaks standard DX cluster
protocol. GTBridge already knows how to connect to DX cluster telnet servers.
Just point it at the Windows box IP:7300. Gives real-time local CW spots
without the RBN round-trip delay.

Spot format is standard cluster:
```
DX de YOURCALL:  14023.5  W1AW        22 dB  28 WPM  CQ      1845Z
```

### RBN Feed (No Changes Needed)

Spots flow: HL2 → SkimSrv → Aggregator → RBN → cluster node → GTBridge.
Already works with existing GTBridge cluster connection. Slight delay through
the RBN pipeline. Your own spots mixed in with everyone else's.

### Future: Dedicated skimmer.py Module

Could build a `skimmer.py` source module for GTBridge (like `pota.py`/`sota.py`)
that:
- Connects to SkimSrv telnet for CW spots
- Reads CWSL_DIGI output for FT8/FT4 spots
- Tags spots as "LOCAL" or "SKIMMER" in GridTracker
- Zero-latency, no RBN dependency
- Could deduplicate against RBN spots to avoid doubles
- Smart polling similar to POTA module's change detection

The SkimSrv telnet connection is the easiest path — it's just another
cluster source. CWSL_DIGI spot capture would need more investigation into
what local output formats it supports (file logging, UDP, etc).

## Key References

| Resource | URL |
|----------|-----|
| M1GEO HL2 + SkimSrv guide | https://www.george-smart.co.uk/2020/12/using-cw-skimmer-with-hermes-lite-2-sdr/ |
| G4IRN Red Pitaya + CWSL_DIGI | https://www.g4irn.com/home/articles-information/cw-ft-modes-skimmer-using-a-red-pitaya-skimsrv-and-cwsl_digi |
| SM7IUN FT8 Skimmer | https://sm7iun.se/redpitaya/ft8skimmer/ |
| HermesIntf (K3IT) | https://github.com/k3it/HermesIntf |
| HermesIntf (KV4TT fork) | https://github.com/KV4TT/HermesIntf |
| CWSL_DIGI | https://github.com/alexranaldi/CWSL_DIGI |
| CWSL shared memory | https://github.com/HrochL/CWSL |
| DigiSkimmer | https://github.com/lazywalker/DigiSkimmer |
| JvanKatwijk cwskimmer | https://github.com/JvanKatwijk/cwskimmer |
| HL2 gateware | https://github.com/softerhardware/Hermes-Lite2 |
| HL2 gateware wiki | https://github.com/softerhardware/Hermes-Lite2/wiki/Updating-Gateware |
| RBN Aggregator guide (PDF) | https://cms.reversebeacon.net/sites/cms.reversebeacon.net/files/2019/12/21/Using%20Aggregator%20-%20v6.0.pdf |
| Afreet SkimSrv | http://www.dxatlas.com/cwskimmer/ |
| N6TV Skimmer/RBN presentation | https://www.kkn.net/~n6tv/N6TV_Dayton_2017_CW_Skimmer.pdf |
