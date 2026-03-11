# XTS5000 Non-Affiliate MARCS/BRICS Monitoring Setup

Notes on programming a Motorola XTS5000 for receive-only P25 trunked monitoring on the MARCS/BRICS system (Butler County, OH). No system key needed for receive-only.

## Software

- **ASTRO25 Portable Depot R20.01.00** (recommended) — verified clean, no malware. Depot is a superset of CPS with higher privileges. **Bypasses the system key requirement entirely** — just enter the radio's flashcode when creating a codeplug and trunking menus are fully accessible. Cannot be installed alongside CPS (must uninstall CPS first).
- **ASTRO25 Portable CPS R20.01.00 + Tuner** — verified clean, no malware. Requires a system key to unlock trunking menus. Use only if Depot is unavailable.
- **PatPortDepot.exe** / **PatPort.exe** — run after installing Depot/CPS to unlock licensing
- Install in a **Hyper-V VM** (Windows 10 Pro) to keep cracked software isolated from your main PC. Take checkpoints before and after install.
- **Programming cable**: RPC-M5K-U (USB, compatible with RKN4105). Plug and play, no driver needed. Works on XP/7/10/11. USB passthrough via Hyper-V Enhanced Session Mode.

## System Key

**If using Depot: no system key needed.** Depot bypasses the key requirement — just enter the radio's flashcode (from the eBay listing, radio label, or read from the radio) when creating a new codeplug, and trunking menus unlock automatically.

If using CPS instead of Depot, a system key is required to unlock trunking features. It does **not** need to match the actual MARCS system — any valid key for any system ID will unlock the trunking menus.

- **BatLabs hex editor method**: 27-byte file with fixed header + 3 bytes derived from any SysID via lookup table. Save as `sys0xxxx.key` where xxxx is the SysID.
- **DOS keygen (syskey.exe)**: Original Motorola tool, runs in DOSBox. Generates key files.
- **Rust keygen (k4yt3x/syskey on GitHub)**: Modern rewrite but generates a smaller key file that doesn't work with ASTRO 25 CPS — the file size is wrong. ASTRO 25 CPS expects a slightly larger key file than the older RSS software.
- Load key in CPS via **File > Import > Software System Key**
- Once loaded, trunking personality and talkgroup menus become accessible

## CPS Programming Walkthrough

### 1. Radio Wide Settings

Under **Radio Configuration > Radio Wide**:
- **Disable Man Down / Emergency** — prevents transmitting emergency data to the system
- **Disable Motorola Proprietary ("Pop") Feature** — under ASTRO 25 tab, uncheck this to prevent the radio from phoning home to the control system
- Optional: remap orange button (e.g., backlight toggle)
- Optional: enable radio alias to display callsign on screen

### 2. Trunking System Setup

Under **Trunking > System**:
- **System ID**: enter as hex (e.g., `262` for Indianapolis example). Get from RadioReference.
- **Unit ID**: can be anything — radio is not transmitting or registering
- **Control Channel Frequencies** (under Frequencies tab):
  - Enter **receive frequencies only** — these are the control channels
  - Use only the control channels and backups (marked in red on RadioReference)
  - Do NOT add all system frequencies — causes delay and audio distortion
  - **Transmit frequency**: set to a frequency known to be unused/harmless (extra safety layer)
- **Data tab**: **Disable PCAP** (packet data) — prevents the radio from sending data bursts/probes to the system. Leaving this enabled risks the system detecting the radio.
- **ASTRO 25 tab**: **Uncheck Motorola Proprietary Features** — prevents registration/phone-home behavior

### 3. Trunking Personalities (Talkgroups)

Under **Trunking > Personalities**:
- Select the system (e.g., System 1)
- Set to **P25** (Phase 1) protocol
- Add talkgroups using **hex** values from RadioReference (not decimal)
  - RadioReference shows both DEC and HEX — use the HEX value
  - Traditional scanners use DEC; Motorola radios use HEX
- Keep notes mapping talkgroup hex IDs to names — CPS only shows the hex, not the name

### 4. Conventional Channels (1-16)

Under **Conventional Channels**:
- Create 16 channels even if not all are used (easier to add later)
- For each channel:
  - **Receive Only**: check this — marks the personality as listen-only
  - **Mode**: set to **Astro** (works better on P25 systems, less interference)
  - **Autoscan**: check this
  - **Scan List**: map to the corresponding scan list (channel 1 -> scan list 1, etc.)
- Name channels descriptively (e.g., "All Scan", "FD Dispatch", "PD North")

### 5. Zone Setup

Under **Zones**:
- Create zone(s) as needed (e.g., "MARCS", "Butler Co")
- Channel layout per zone:

| Channels | Type | Purpose |
|----------|------|---------|
| 1-16 | Conventional (CW type) | User-accessible via knob. Each slaved to a trunked scan list |
| 17+ | Trunked personality (TG type) | Actual talkgroup entries. NOT directly accessible from knob |

- Map each conventional channel to its personality
- Map each trunked personality to its talkgroup
- Use the same name for conventional channel and its corresponding talkgroup personality to avoid confusion

Since the radio can only access channels 1-16 via the knob/menu, it can never land on a trunked personality directly, which means it **cannot affiliate** with the system.

### 6. Scan Lists

Under **Scan Lists**:
- Create 16 scan lists (one per conventional channel) — keep numbering 1:1 with channels
- For each scan list:
  - Select **zone** and **talkgroup channel(s)** (17+) to include
  - Channel 1 / Scan List 1 can be "All Scan" — includes all talkgroups
  - Other channels can be mapped to individual talkgroups or smaller groups
- **Important**: set scan list members to trunked channels (17+), NOT conventional (1-16)
- Map each scan list back to its conventional channel under the channel's scan settings

### Mapping Summary

```
Conventional Ch 1 -> Scan List 1 -> Talkgroup(s) at Ch 17, 18, 19...  (All Scan)
Conventional Ch 2 -> Scan List 2 -> Talkgroup at Ch 17              (FD Dispatch)
Conventional Ch 3 -> Scan List 3 -> Talkgroup at Ch 18              (PD Primary)
...
```

Keep a spreadsheet or notepad mapping channels to scan lists to talkgroup hex IDs and names. This is critical for troubleshooting — CPS does not make this easy to visualize.

## Safety Precautions

Multiple layers of protection to ensure the radio never transmits or interacts with the system:

1. **Disable PCAP** (Trunking System > Data) — no packet data/probes sent to system
2. **Disable Proprietary Features** (Trunking System > ASTRO 25 tab) — no registration/phone-home
3. **Disable Man Down / Emergency** (Radio Wide) — no emergency transmissions
4. **Receive Only Personality** checked on each conventional channel
5. **Bogus transmit frequency** — even if TX occurs, it goes somewhere harmless
6. **TX Inhibit** — but note: can cause the radio to miss traffic on some systems
7. **No valid subscriber/radio ID** — system can't target or brick the radio
8. **NAS method** — trunked personalities hidden behind channel 16, radio can't affiliate
9. **No RSM (remote speaker mic)** — eliminates accidental PTT

### Pre-deployment Verification

- Double and triple check codeplug before writing to radio
- **Fully charge battery before writing** — power loss during write can brick the radio
- Save original codeplug immediately after first read from radio
- Date each codeplug save for easy rollback
- Optional: verify no RF output with dummy load + spectrum analyzer (TinySA) before connecting antenna

## Gotchas

- **Simulcast systems**: MARCS is simulcast — the XTS5000 handles this better than most scanners
- **Forced affiliation**: Not a thing on standard Motorola ASTRO 25 P25 systems. Mostly an OpenSky feature. MARCS should work fine without affiliation.
- **System key**: A key is needed to unlock trunking in CPS, but any valid key works — it doesn't have to match the target system. The Rust/BatLabs keygens produce the correct 27-byte key data but output it raw — CPS expects a 9-byte header + PRNG-XOR encrypted payload wrapper (see `batwing-cps-key-RE-notes.md`). Use Batwing's encoder (`batwing-syskey-encoder.py`) to generate properly formatted .KEY files, or just use Depot + flashcode to bypass the key entirely.
- **Phase 2**: P25 Phase 2 systems may not be monitorable with this method. MARCS is Phase 1, so not a concern.
- **Talkgroup IDs**: Motorola radios use **hex** values, not decimal. RadioReference lists both — use the hex column.
- **Too many control channels**: Adding all system frequencies instead of just control channels causes delay and audio distortion. Stick to control + backups.
- **Codeplug development**: Start simple (1-2 talkgroups), verify it works, then add more. Save dated versions as you go so you can revert if something breaks.
- **Cloning**: If buying multiple XTS5000s, make sure they match (same model/options). CPS can clone codeplugs between matching radios via Tools > Cloning.
- **No-screen radios**: If the XTS5000 variant has no display, you can't see channel names — notes/spreadsheet becomes essential.

## Resources

- RadioReference.com — Butler County/MARCS talkgroup lists, control channel frequencies (red = control)
- BatLabs (batlabs.com) — Motorola programming reference, system key info (intermittently available)
- YouTube — W9FMS (Brian Blackburn) XTS5000 NAS programming walkthrough
- W3AXL Wiki — Astro25 series radio reference
