# OpenSkimmer — Open Source Linux CW/FT8/RTTY Skimmer

## Vision

A complete, open-source replacement for the Windows skimmer stack (SkimSrv + CWSL_DIGI + RTTYSkimSrv + RBN Aggregator) that runs on Linux in a single container or bare metal installation.

**Why:** Because a skimmer doesn't need a dedicated Windows box with archaic configs and a GUI to do what should really be done command line on a Linux box — possibly even in a container. Something where if it breaks you spin up another container or restore from a backup, not reload a whole machine. The current Windows skimmer stack requires GUI-only configuration, suffers from DLL version hell, Armadillo copy protection lockouts, and dedicates an entire computer to a task that should be a headless service.

**Goal:** `docker run openskimmer --config skimmer.json` — done.

## Architecture

```
Red Pitaya STEMlab (HPSDR Protocol 1, 192kHz x 8 bands)
    |
    v  [UDP IQ stream]
hpsdr_receiver (reads IQ, splits to per-band ring buffers)
    |
    ├── cw_skimmer (CW decoding, all bands simultaneously)
    |       Based on: csdr-skimmer + AG1LE Bayesian decoder
    |
    ├── ft_skimmer (FT8/FT4/FT4 decoding, all bands)
    |       Based on: jt9 from WSJT-X (already compiles on Linux)
    |
    ├── rtty_skimmer (RTTY decoding, all bands)
    |       Based on: fldigi RTTY engine or multimon-ng
    |
    v
spot_aggregator (combines all spots, dedup, output)
    |
    ├── RBN feed (telnet output, replaces Windows RBN Aggregator)
    ├── PSK Reporter feed (UDP)
    ├── DX cluster telnet server (for GTBridge or any cluster client)
    └── WSJT-X UDP output (direct to GridTracker if desired)
```

One IQ stream → three decoders → one aggregator → multiple outputs.

## What It Replaces

| Windows Stack | OpenSkimmer Equivalent |
|---|---|
| SkimSrv (Afreet, closed source, Armadillo DRM) | cw_skimmer (csdr-skimmer fork, GPL-3) |
| CWSL_DIGI (open source, but Windows-only jt9.exe) | ft_skimmer (jt9 compiled natively on Linux) |
| RTTYSkimSrv (Afreet, closed source) | rtty_skimmer (fldigi engine, GPL-3) |
| CWSL_Tee.dll (shared memory bridge) | Not needed — direct IQ pipe between components |
| HermesIntf.dll (HPSDR interface) | hpsdr_receiver (Python/C, native HPSDR protocol) |
| RBN Aggregator (closed source Windows GUI) | spot_aggregator (Python, headless, JSON config) |
| Windows Task Scheduler (day/night switching) | Built-in sunrise/sunset config (astral library) |

**Total Windows programs replaced: 6**
**Total DLLs eliminated: 3**
**Total GUIs eliminated: 4**
**Armadillo copy protection lockouts: 0**

## Built On (Credit Where Credit Is Due)

This is derivative work, built on the contributions of others. All components are properly licensed and attributed.

- **csdr-skimmer** by luarvique — C++, GPL-3. Multi-signal CW/RTTY skimmer built on CSDR DSP library. Used by OpenWebRX. The foundation for the CW decoder. [GitHub](https://github.com/luarvique/csdr-skimmer)
- **WSJT-X / jt9** by K1JT (Joe Taylor) et al — GPL-3. The gold standard FT8/FT4 decoder. jt9 compiles natively on Linux. [Source](https://sourceforge.net/projects/wsjt/)
- **fldigi** by W1HKJ (Dave Freese) — GPL-3. Mature RTTY decoder with years of real-world testing. [GitHub](https://github.com/w1hkj/fldigi)
- **AG1LE's Bayesian Morse decoder** — Open source C implementation of VE3NEA's Bayesian approach. 3,335 lines, tested with real contest signals. The algorithm reference for CW decoding improvements.
  - [Towards Bayesian Morse Decoder](http://ag1le.blogspot.com/2013/01/towards-bayesian-morse-decoder.html)
  - [New Morse Decoder Part 1-6](http://ag1le.blogspot.com/2013/09/new-morse-decoder-part-1.html)
  - [Multi-signal detection](http://ag1le.blogspot.com/2012/04/experiment-decoding-multiple-morse-code.html)
  - [deepmorse-decoder on GitHub](https://github.com/ag1le/deepmorse-decoder)
- **VE3NEA (Alex Shovkoplyas)** — Creator of CW Skimmer. His Bayesian approach to CW decoding, as shared with AG1LE, is the conceptual foundation. We use his ideas (not his code) with respect and gratitude.
- **Dr. Bell's doctoral thesis** — The mathematical foundation for Bayesian Morse decoding, referenced by AG1LE as "one of the best and most comprehensive documents on this topic."
- **OpenHPSDR community** — HPSDR Protocol 1 specification and open source implementations.
- **Pavel Demin** — Red Pitaya SDR Alpine images and sdr_receiver_hpsdr firmware. [GitHub](https://github.com/pavel-demin/red-pitaya-notes)
- **rx4000.py** from Hermes-Lite2 repo — Working Python HPSDR Protocol 1 IQ receiver. [Source](https://github.com/softerhardware/Hermes-Lite2/blob/master/software/ft8/rx4000.py)
- **JvanKatwijk/cwskimmer** — C++/Qt CW skimmer with clear architecture documentation. [GitHub](https://github.com/JvanKatwijk/cwskimmer)
- **MorseAngel** by f4exb — Python/PyTorch LSTM Morse decoder. [GitHub](https://github.com/f4exb/morseangel)

## Testing Strategy

Run OpenSkimmer on the G3 (bare metal Ubuntu) alongside SkimSrv on the G5 (Windows), both reading IQ from the same Red Pitaya simultaneously. Compare spot-for-spot:

- What did SkimSrv decode that OpenSkimmer missed? (accuracy gap)
- What did OpenSkimmer catch that SkimSrv didn't? (potential advantage)
- Frequency accuracy comparison (skew measurement)
- CPU usage comparison
- Latency comparison

The Windows stack stays as the reference until OpenSkimmer matches or exceeds it. Then the G5 gets wiped and becomes something useful.

**Offline development with recorded IQ samples:**
The primary development workflow uses recorded IQ samples, NOT live hardware:
1. Record IQ samples from the pitaya (various conditions: contest, DX, weak signals, mixed WPM)
2. Run recordings through SkimSrv on the G5 to get reference decodes (the "answer key")
3. Run same recordings through OpenSkimmer and diff the output
4. Iterate until the diff is small
5. Claude writes code and tests against recordings — no hardware sharing needed
6. Live hardware integration is only for final testing

**Test suite to build:**
- Strong contest signals (20+ dB, 20-35 WPM) — easy baseline
- Weak DX signals (S1-S3) — the hard stuff
- Pileups with overlapping signals on adjacent frequencies — hardest
- Mixed WPM speeds (15 WPM next to 40 WPM) — adaptive speed test
- QRM/QRN conditions — real-world noise
- Band edges with signal wrap — edge cases

This approach lets Claude develop and test at 3am without touching the radio.

**Contest IQ recordings as training data:**
The contest community is a goldmine — operators record full IQ of entire contests for dispute resolution. These recordings plus published contest logs create a perfect supervised dataset:
1. Get contest IQ recordings (ask club members, contest reflectors, archives)
2. Get published contest logs from ARRL/CQ (public after contest deadline)
3. Cross-reference: logs show exactly who was on what frequency at what time — the "answer key"
4. Run recordings through SkimSrv for baseline decode counts
5. Run through OpenSkimmer and diff
6. Every missed signal is a training opportunity for ML decoders
7. Every false positive is a bug to fix
8. Thousands of hours of real-world CW at every speed, signal level, and condition — for free

Sources for IQ recordings:
- **DK3QN 40m contest WAV** — http://www.dk3qn.com/wfSDRwav.htm (real CW contest, ready to use)
- **CQ WW CW 2005 IQ** — 96kHz on 7040, in OpenWebRX GitHub PR #87
- **HamSCI/Zenodo 192kHz recordings** — https://zenodo.org/records/848699 (40m), /851361 (40m pt2), /853500 (15m), /883046 (10m) — exact skimmer format, QS1R + CWSL_File
- **CWSL_File** — record from your own pitaya via SkimSrv shared memory (HrochL/CWSL GitHub)
- **SDRplay demo files** — https://www.sdrplay.com/iq-demo-files/
- **IQEngine** — https://iqengine.org/ (community IQ recording repository)

Answer keys for validation:
- **RBN raw data** — https://www.reversebeacon.net/raw_data/ (daily CSVs, every CW spot from every skimmer, 300K+ spots during contest weekends)
- **ARRL public logs** — https://contests.arrl.org/publiclogs.php (Cabrillo files, ground truth)
- **RBN analysis tools** — https://github.com/N7DR/rbn-analysis

ML training resources:
- **AG1LE deepmorse-decoder** — https://github.com/ag1le/deepmorse-decoder (27.8 hrs, 97.2% accuracy)
- **MorseCodeToolkit** — https://github.com/1-800-BAD-CODE/MorseCodeToolkit (synthetic data generator)
- **MorseAngel** — https://github.com/f4exb/morseangel (PyTorch LSTM decoder)
- **morse-dataset** — https://github.com/souryadey/morse-dataset (synthetic, ICCCNT 2018 Best Paper)
- **cw-rtty-modem** — https://github.com/kgoba/cw-rtty-modem (ML-based, author active in WSJT-X dev)

**IQ distribution note (for live testing):** HPSDR Protocol 1 is point-to-point UDP. To feed both the G5 and G3 simultaneously, use either:
- `udp_relay.py` on the G5 to duplicate IQ packets to the G3
- Multicast configuration on the Red Pitaya (if supported by Pavel Demin's firmware)
- Or a network TAP/mirror port on the SG300

## Development Phases

### Phase 1: "It spots things" (1-2 weekends) — DONE (2026-03-17)
- Fork csdr-skimmer — DONE, builds on Linux
- Basic CW decoding — DONE, 80 validated callsigns from test WAV
- Compare against SkimSrv — DONE, 28 matching + 52 exclusive finds
- **BREAKTHROUGH: Multi-pass brute force decoding**
  - 3 decoder tunings × 12 bandwidths × 3 inputs × 3 thresholds = 324 passes
  - Merge all raw output through master.scp validation
  - Results: **107 validated calls vs CW Skimmer's 108** (99% match!)
  - Found **60 calls CW Skimmer missed entirely**
  - 47 calls matching CW Skimmer's output
  - Critical discovery: 33 of CW Skimmer's 108 calls were missing from MASTER.SCP
  - The decoder quality was never the bottleneck — the database was
  - Approach: brute force with smart filtering beats elegant single-pass decoding
  - Automated runner: `run_multipass.sh`
- Still needed: HPSDR Protocol 1 input for live operation, DX cluster output

### Phase 2: "It spots things well" (primary approach: SDC-style callsign optimization)
- **Primary: callsign-optimized decoding** — don't try to decode all CW text, just find callsign patterns
  - Decode rough characters from CW timing
  - Pattern match against callsign formats (1-2 letters + 1-2 digits + 1-3 letters)
  - Validate against **master.scp** (Super Check Partial — database of all known callsigns)
  - If match: spot it. If no match: discard. master.scp does the heavy lifting.
  - Add configurable SNR threshold and blacklist support
  - This is how SDC (UT4LW) beats CW Skimmer while using minimal CPU
- **Fallback: AG1LE Bayesian decoder** — if callsign-optimized isn't accurate enough, upgrade the timing classifier with probabilistic element classification (keep this in reserve)
- Add jt9 integration for FT8/FT4
- Add fldigi RTTY integration
- Build spot_aggregator with RBN + PSK Reporter output
- Sunrise/sunset auto band switching
- Docker container packaging

**SDC design philosophy (closed source, but the model to follow):**
- Created by Yuri UT4LW — donationware at lw-sdc.com
- Outperforms CW Skimmer at callsign spotting, handles speed changes better, minimal CPU
- master.scp validation eliminates false spots
- Users on FlexRadio forums report giving up CW Skimmer entirely
- We use the approach (callsign-optimized + master.scp gating), not the code

### Phase 3: "It replaces the Windows stack" (spring goal)
- Match SkimSrv at 90%+ accuracy on CW callsign extraction
- Full FT8/FT4/RTTY decoding
- Production-ready deployment
- Documentation for community deployment
- G5 gets wiped, OpenSkimmer runs on G3 or in a container

### Phase 4: "Community contribution" (ongoing)
- GitHub release with Docker images
- Documentation for Red Pitaya + OpenSkimmer setup
- Support for other SDRs (Airspy, KiwiSDR, RTL-SDR)
- Integration with GTBridge and dxfilter
- Community testing and improvement

## Configuration (Target)

```json
{
    "callsign": "WF8Z-2",
    "grid": "EM79sm",
    "sdr": {
        "type": "hpsdr",
        "host": "192.168.1.54",
        "receivers": 8,
        "sample_rate": 192000,
        "bands": ["80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"]
    },
    "decoders": {
        "cw": {"enabled": true, "min_wpm": 10, "max_wpm": 50},
        "ft8": {"enabled": true, "depth": 2},
        "ft4": {"enabled": true},
        "rtty": {"enabled": true}
    },
    "output": {
        "rbn": {"enabled": true, "host": "telnet.reversebeacon.net", "port": 7000},
        "pskreporter": {"enabled": true},
        "telnet": {"enabled": true, "port": 7550},
        "wsjtx_udp": {"enabled": false, "host": "192.168.1.205", "port": 2237}
    },
    "schedule": {
        "auto_switch": true,
        "grid": "EM79sm",
        "day_offset_min": 30,
        "night_offset_min": 30
    }
}
```

One JSON file. One process. Zero Windows.

## The Bottom Line

> "A skimmer doesn't need a dedicated Windows box with archaic configs and a GUI to do what should really be done command line on a Linux box. That software has no business running on a winbox." — WF8Z

> "Why are we doing this? Because I don't like Windows." — Also WF8Z
