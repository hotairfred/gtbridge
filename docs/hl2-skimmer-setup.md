# Hermes Lite 2 Skimmer Setup Guide

Turn your spare HL2 into a multi-band CW + FT8/FT4 skimmer feeding spots to
GridTracker via GTBridge. All software runs on the spare Windows box in the shack.

## What You'll End Up With

```
HL2 (10-RX gateware, no TX)
  |  HPSDR UDP
  v
CW Skimmer Server (SkimSrv) --- HermesIntf DLL
  |                          \
  | CW spots (telnet :7300)   \  shared memory (CWSL)
  |                            \
  v                             v
Aggregator -----> RBN      CWSL_DIGI (FT8/FT4/JT65/WSPR decoder)
                               |
                               +--> PSK Reporter
                               +--> Aggregator --> RBN (port 2215)
```

SkimSrv's built-in telnet server on port 7300 outputs DX cluster format spots.
GTBridge can connect to it as a cluster source for local skimmer spots, or you
can just let spots flow through RBN and pick them up on your normal cluster feed.

## Parts List

| Item | Where to Get It | Notes |
|------|----------------|-------|
| HL2 with 10-RX gateware | GitHub: softerhardware/Hermes-Lite2 | Free firmware flash |
| CW Skimmer Server (SkimSrv) | http://www.dxatlas.com/cwskimmer/ | ~$75, 30-day trial |
| HermesIntf DLL | GitHub: k3it/HermesIntf | Free, use KV4TT fork |
| CWSL | GitHub: HrochL/CWSL | Free, shared memory bridge |
| CWSL_DIGI v0.88 | GitHub: alexranaldi/CWSL_DIGI | Free |
| RBN Aggregator | reversebeacon.net | Free, only if feeding RBN |
| WSJT-X | sourceforge | Free, needed for jt9 decoder |
| MS Visual Studio 2022 Redist | Microsoft | Free |
| Intel Fortran Redist | Intel | Free |

## Step 1: Flash 10-RX Gateware on the HL2

This swaps the TX logic for extra receivers: 10 RX slices, no transmit.

1. Download the RX-only gateware `.rbf` file from:
   `https://github.com/softerhardware/Hermes-Lite2/tree/master/gateware/bitfiles`

   Look for: `stable/<version>/variants/hl2b5up_cicrx/hl2b5up_cicrx.rbf`
   (use `hl2b5up` for board v5 and up, which is most HL2s)

2. Flash using **SparkSDR** (easiest):
   - Run SparkSDR, click the discovery button (rotating arrow) until HL2 appears
   - Right-click the HL2, select "Firmware"
   - Navigate to the `.rbf` file, click Program (~1 minute)
   - Power-cycle the HL2 after flashing

   Or use **Quisk**: Config > Radio > "Program from RBF file"

3. Verify: reconnect in SparkSDR or Quisk, confirm you see 10 RX slices
   and no TX capability.

**To go back to normal:** flash the standard `hl2b5up_main.rbf` the same way.

## Step 2: Install CW Skimmer Server (SkimSrv)

1. Download and install from http://www.dxatlas.com/cwskimmer/
   - You want **Skimmer Server**, not the regular CW Skimmer
   - 30-day trial, then $75 for a license

2. Download the **HermesIntf DLL** — use the KV4TT version for better
   watchdog timer handling:
   `https://github.com/KV4TT/HermesIntf/releases`

   Copy `HermesIntf.dll` to: `C:\Program Files (x86)\Afreet\SkimSrv\`

   - If you have multiple HPSDR radios on the network (like your Flex),
     rename the DLL to lock it to the HL2's IP:
     `HermesIntf_192.168.1.xxx.dll` (use your HL2's IP)

3. Configure SkimSrv:
   - Right-click the system tray icon to open settings
   - Select `HermesIntf` as the radio
   - Set number of receivers to **10**
   - Sample rate: **192 kHz** (widest bandwidth per slice)
   - Select bands you want to skim (160 through 6m)
   - Enable the built-in Telnet server (default port 7300)

4. Start SkimSrv. You should see the waterfall display and CW decodes
   appearing. Test by connecting: `telnet localhost 7300`

   You'll see standard DX cluster format spots like:
   ```
   DX de YOURCALL:  14023.5  W1AW        22 dB  28 WPM  CQ      1845Z
   ```

## Step 3: Install CWSL (Shared Memory Bridge)

CWSL bridges audio from SkimSrv's shared memory to CWSL_DIGI.

1. Download from: `https://github.com/HrochL/CWSL`
2. Copy `CWSL_Tee.dll` into the SkimSrv program folder:
   `C:\Program Files (x86)\Afreet\SkimSrv\`
3. Restart SkimSrv — CWSL_Tee will load automatically and make receiver
   audio available via shared memory.

## Step 4: Install CWSL_DIGI

1. Install prerequisites:
   - WSJT-X (for the jt9 decoder binary)
   - Microsoft Visual Studio 2022 C++ Redistributable (x64)
   - Intel Fortran Redistributable

2. Download CWSL_DIGI v0.88 from:
   `https://github.com/alexranaldi/CWSL_DIGI/releases`

3. Extract to a folder NOT in Program Files (Windows permissions issues):
   `C:\CWSL_DIGI\`

4. Edit `config.ini`:

```ini
[operator]
callsign=YOURCALL
gridsquare=AB12cd

[radio]
# Set to -1 for single receiver, or number of receivers
sharedmem=-1

[decoders]
# Uncomment the bands/modes you want. One line per band+mode.
# Format: decoder=frequency_hz mode
# FT8 on common bands:
decoder=1840000 FT8
decoder=3573000 FT8
decoder=7074000 FT8
decoder=10136000 FT8
decoder=14074000 FT8
decoder=18100000 FT8
decoder=21074000 FT8
decoder=24915000 FT8
decoder=28074000 FT8
decoder=50313000 FT8
# FT4:
decoder=3575500 FT4
decoder=7047500 FT4
decoder=10140000 FT4
decoder=14080000 FT4
decoder=21140000 FT4
decoder=28180000 FT4

[wsjtx]
# Point to your WSJT-X install
binpath=C:\WSJT\wsjtx\bin

[reporting]
# Enable what you want:
pskreporter=true
rbn=true
wsprnet=false
```

   **Important:** Decoder frequencies must fall within the bandwidth of a
   SkimSrv receiver slice. At 192 kHz sample rate, each slice covers 192 kHz
   centered on the band. Make sure SkimSrv has a receiver assigned to each
   band you list here.

5. Run from a command prompt (so you can see errors):
   ```
   cd C:\CWSL_DIGI
   CWSL_DIGI.exe
   ```

## Step 5: RBN Aggregator (Optional — Only If Feeding RBN)

Skip this if you only want local spots. If you want to contribute to RBN:

1. Download Aggregator from reversebeacon.net
2. Configure:
   - Main tab: connect to SkimSrv telnet (`localhost:7300`), enter your callsign
   - FT# tab: check source **40**, verify port **2215**
   - Status page should show CW spots from SkimSrv and FT spots from CWSL_DIGI

## Step 6: Connect GTBridge to Local Skimmer

### Option A: Direct Telnet (CW spots only, immediate)

SkimSrv's telnet on port 7300 speaks DX cluster protocol. Add it as a
cluster source in `gtbridge.json`:

```json
{
    "dx_cluster": {
        "host": "192.168.1.xxx",
        "port": 7300,
        "callsign": "YOURCALL"
    }
}
```

Replace the IP with your Windows box. This gives you real-time local CW
skimmer spots in GridTracker without the RBN round-trip.

### Option B: RBN Feed (CW + digi, slight delay)

Just connect GTBridge to an RBN-aware cluster node as usual. Your own
skimmer spots will appear mixed in with everyone else's after a short delay
through the RBN pipeline.

### Option C: Local Skimmer Module (Future)

We could build a dedicated `skimmer.py` module for GTBridge that:
- Connects to SkimSrv telnet for CW spots
- Reads CWSL_DIGI output for FT8/FT4 spots
- Tags them as local skimmer spots in GridTracker
- Gives zero-latency local decodes without RBN dependency

This would be similar to how `pota.py` and `sota.py` work — a dedicated
source that feeds into the bridge's spot pipeline.

## Frequency Calibration

**Do this before feeding spots to RBN/PSK Reporter!**

The HL2's oscillator drifts slightly. Bad calibration = wrong spot frequencies.

1. In SkimSrv, adjust `FreqCalibration` in SkimSrv.ini until known-frequency
   signals (like WWV or NIST) read correctly.
2. In CWSL_DIGI config.ini, set the reciprocal value:
   - If SkimSrv = `0.999998765`, CWSL_DIGI = `1.000001235`
3. Monitor accuracy on SM7IUN's RBN analytics page after you go live.

## Tips and Gotchas

- **Antenna:** Use a separate wideband RX antenna, not your Flex TX antenna.
  A long wire, loop, or discone works fine for skimming — you're just
  listening. Keep it away from the Flex's TX antenna to avoid desense.

- **Network:** The HL2 uses HPSDR protocol over UDP. Make sure it's on the
  same subnet as the Windows box. If you have VLAN issues, the HL2 needs
  to be reachable directly (no routing).

- **Flex coexistence:** HermesIntf DLL will try to talk to any HPSDR device
  it finds. If your Flex is on the same network, **rename the DLL** to lock
  it to the HL2's IP address (see Step 2).

- **WDT drops:** If SkimSrv keeps disconnecting from the HL2, use the KV4TT
  version of HermesIntf — it handles the watchdog timer better than the
  original k3it version.

- **Performance:** 10 slices decoding CW + FT8/FT4 across all bands is
  CPU-heavy. Expect 20,000+ spots/day. The spare box should be dedicated
  to this — don't run other heavy stuff on it.

## References

- M1GEO guide: https://www.george-smart.co.uk/2020/12/using-cw-skimmer-with-hermes-lite-2-sdr/
- G4IRN Red Pitaya + CWSL_DIGI guide: https://www.g4irn.com/home/articles-information/cw-ft-modes-skimmer-using-a-red-pitaya-skimsrv-and-cwsl_digi
- HermesIntf: https://github.com/k3it/HermesIntf
- KV4TT HermesIntf fork: https://github.com/KV4TT/HermesIntf
- CWSL_DIGI: https://github.com/alexranaldi/CWSL_DIGI
- CWSL: https://github.com/HrochL/CWSL
- HL2 gateware: https://github.com/softerhardware/Hermes-Lite2/tree/master/gateware/bitfiles
- HL2 gateware update wiki: https://github.com/softerhardware/Hermes-Lite2/wiki/Updating-Gateware
- SM7IUN FT8 Skimmer: https://sm7iun.se/redpitaya/ft8skimmer/
- RBN Aggregator guide: https://cms.reversebeacon.net/sites/cms.reversebeacon.net/files/2019/12/21/Using%20Aggregator%20-%20v6.0.pdf
