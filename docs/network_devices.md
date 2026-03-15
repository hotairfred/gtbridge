---
name: Network device inventory
description: Full IP/MAC/device mapping for Fred's home network with switch port assignments
type: reference
---

## Network Diagram

```
                                Internet
                                   |
                            [MikroTik .1]
                          RB5009UG+S+IN
                                   |
              ┌────────────────────┴────────────────────┐
              │                                         │
       [SG300 "core" .251]                      [SG350 "office" .250]
       Basement/Shack, 24-port                  Upstairs/Office, 10-port
              │                                         │
   ┌────┬────┬┼────┬─────┬─────┐            ┌─────┬────┤
   │    │    │ │    │     │     │            │     │    │
  gi4  gi5  gi6 gi7 gi9  gi10  gi12 ←────→ gi3   gi4  gi7
   │    │    │   │   │     │    uplink       uplink │    │
  .194  │    │   │   │     │                       │    │
  PC    │    │   │   │     │                       │    │
        │    │   │   │     │                   Deb's  Fred's
      Flex Pitaya G5 Shack Proxmox             PC     PC
      .238 .54  .28  PC   .101               .21    .205
                     .117  + containers              │
                           .36 AI (Grayline)    SmartSDR
                           .26 Docker          GridTracker
                           .25 Zammad           WSJT-X
                           .9  Pi-hole
                                   │
                                  gi1
                                   │
                            [3650G Bedroom]
                          Old Cisco (RETIRING)
                                   │
              ┌────┬─────┬────┬────┼────┬────┐
             Gi0/5 Gi0/7 0/11 0/15 0/19 0/21 0/24
              │     │          │    │    │     │
           Living  OMV      Garage Garage SG350 IoT/Rokus
           Room    HA       switch switch gi1   Weather
           .2      .18     100Mbps 100M  uplink Ant Switch
           Linksys .236                         .189
           (AnFBIVan) .14
                                         Gi0/12
                                           │
                                      SG300 gi24
                                      (BLOCKED by
                                      spanning tree)

   Legend:
   ←────→  Active uplink (forwarding)
   .xxx    IP address (192.168.1.xxx)
   100Mbps Ports negotiated at 100M (dumb switches)
```

## Key Ham Radio Devices

| IP | MAC | Device | Switch Port |
|---|---|---|---|
| .238 | 00:1C:2D:02:03:95 | **Flex 6700** | SG300 gi5 |
| .54 | 00:26:32:F0:98:04 | **Red Pitaya** (rp-f09804) | SG300 gi6 |
| .28 | E8:D8:D1:3B:BF:EC | **G5 Mini Skimmer** (Bench) | SG300 gi7 |
| .117 | 04:D4:C4:55:18:02 | **Shack PC** (DESKTOP-P07QDKT) | SG300 gi9 |
| .205 | 50:EB:F6:7F:DF:6E | **Fred's PC** (DESKTOP-5VH4EP3) | SG350 gi7 |
| .46 | 00:1C:C0:A2:13:DD | **Hermes Lite 2** | SG300 |
| .209 | 00:90:C7:12:C4:5B | **IC-9700** | SG300? |
| .189 | 78:21:84:80:90:A0 | **Remote Antenna Switch** | SG300? |

## Computers & Servers

| IP | MAC | Device | Switch Port |
|---|---|---|---|
| .101 | BC:24:11:69:0D:C3 | **Proxmox server** (GTBridge, containers) | SG300 gi10 |
| .36 | BC:24:11:F1:60:C0 | **AI container** (Batwing/Grayline) | SG300 gi10 |
| .26 | BC:24:11:21:49:40 | **Docker container** | SG300 gi10 |
| .25 | BC:24:11:01:B0:28 | **Zammad container** | SG300 gi10 |
| .32 | BC:24:11:E6:EB:3C | **TTS container** | SG300 gi10 |
| .33 | BC:24:11:4A:EA:CE | **RTS container** | SG300 gi10 |
| .40 | BC:24:11:49:39:93 | **Proxmox container** | SG300 gi10 |
| .100 | BC:24:11:2E:1E:85 | **Proxmox container** | SG300 gi10 |
| .16 | BC:24:11:97:67:A1 | **Proxmox container** | SG300 gi10 |
| .7 | BC:24:11:7D:0F:0F | **Proxmox container** | SG300 gi10 |
| .4 | F8:B4:6A:A1:17:7A | **Proxmox host?** | SG300 gi10 |
| .21 | 50:EB:F6:CE:42:E4 | **Deb's PC** (DESKTOP-2J8K0KC) | SG350 gi4 |
| .194 | C4:54:44:00:AD:8B | **DESKTOP-4INF6VV** | SG300 gi4 |
| .18 | 6E:7F:87:65:62:99 | **OpenMediaVault** | SG300 gi10? |
| .20 | B8:AC:6F:DD:89:A0 | **File Server 1** | SG300? |
| .15 | E2:0E:F2:12:9F:DA | **Proxmox1** (2nd Proxmox?) | SG300? |
| .230 | 10:E7:C6:11:BA:D9 | **G3 (retired)** | SG300 |
| .34 | 20:4E:F6:97:83:1D | Fred's PC WiFi (same hostname) | SG350? |

## Home Automation / IoT

| IP | MAC | Device | Switch Port |
|---|---|---|---|
| .9 | 7E:D2:50:EE:F0:9C | **Pi-hole 2** (DNS) | SG300 gi10 |
| .14 | AA:B0:76:6A:89:D2 | **Home Assistant** | SG300 gi10? |
| .235 | E4:B0:63:16:B9:3C | **Ecowitt WX** (weather sensor) | via gi12 |
| .228 | 48:E7:29:7C:40:6D | **Weather Station** | via gi12 |
| .24 | D8:BC:38:7F:A3:48 | **WeatherHub** | via gi12 |
| .236 | 66:AB:76:4C:10:2C | **weewx2** (weather software) | via gi12 |
| .52 | 98:F4:AB:F2:72:0C | **Shelly 1PM** (porch) | via gi12 |
| .169 | B0:39:56:E4:25:CB | **VMB4000** (Arlo base?) | via gi12 |
| .173 | 84:CC:A8:A4:42:3F | **WLED** (LED controller) | WiFi |
| .224 | DC:DA:0C:4D:57:D0 | **espressif** (ESP32 device) | via gi12 |
| .185 | C4:5B:BE:48:53:68 | **ESP-485368** | WiFi? |
| .178 | 74:DA:38:41:A5:93 | **HeaterMeter** (BBQ controller) | WiFi? |

## Entertainment / Media

| IP | MAC | Device | Switch Port |
|---|---|---|---|
| .22 | 00:18:DD:05:37:D3 | **HDHomeRun** | via gi12 |
| .171 | A8:51:AB:CE:59:A0 | **Bedroom** (Roku/TV?) | via gi12 |
| .170 | B8:A1:75:E5:7B:93 | **Roku Express** | via gi12 |
| .218 | C0:95:6D:63:14:E0 | **Living Room** (Roku/TV?) | via gi12 |
| .119 | 08:12:A5:28:5E:80 | **Amazon Echo** | via gi12 |

## Network Infrastructure

| IP | MAC | Device | Location |
|---|---|---|---|
| .1 | — | **MikroTik RB5009** (router) | Basement |
| .251 | 34:62:88:6F:7B:02 | **SG300** (24-port managed) | Basement |
| .250 | A4:53:0E:66:F3:EA | **SG350** (10-port managed) | Office |
| — | — | **3650G** (old Cisco) | Bedroom |
| .2 | 60:38:E0:A8:93:BA | **Linksys** (AnFBIVan) | Living room? |
| .198 | B8:27:EB:F8:62:0B | **WiFi Hotspot** (RPi?) | ? |

## Other / Unknown

| IP | MAC | Device |
|---|---|---|
| .12 | 4E:67:64:73:29:B0 | ? |
| .13 | 04:E9:E5:1B:78:A7 | ? |
| .17 | CA:48:82:91:67:A1 | **BI Server** |
| .23 | 9A:B4:4D:7A:18:FA | **LibreNMS** |
| .30 | 0C:EA:14:5F:7F:19 | ? |
| .31 | 0C:EA:14:5F:7D:C1 | ? (same OUI as .30) |
| .39 | 38:22:E2:2A:DC:FB | ? (same MAC as .210) |
| .44 | 34:62:88:6F:7B:02 | SG300 self MAC |
| .49 | 36:EF:95:21:5B:79 | ? |
| .50 | 1E:31:52:B4:22:A1 | ? |
| .51 | F6:D2:5B:77:91:CA | ? |
| .55 | F6:0B:E5:2D:65:62 | ? |
| .77 | 98:48:27:3F:FC:89 | ? |
| .168 | 00:13:EF:11:0B:49 | **WIN-H58H25735SB** |
| .176 | 44:39:C4:38:58:A8 | **DESKTOP-F8BMMSJ** |
| .210 | 38:22:E2:2A:DC:FB | ? (same MAC as .39) |
| .232 | D8:3A:DD:AD:D7:31 | **packet** |

## Switch Port Mapping

### SG300 (192.168.1.251) — Basement/Shack, 24-port

| Port | Devices |
|---|---|
| gi1 | F4:1E:57:EF:1A:9A — Unknown |
| gi4 | .194 DESKTOP-4INF6VV |
| gi5 | **.238 Flex 6700** |
| gi6 | **.54 Red Pitaya** |
| gi7 | **.28 G5 Mini Skimmer** |
| gi9 | **.117 Shack PC** |
| gi10 | **.101 Proxmox** + all containers (BC:24:11:*) |
| gi12 | **Uplink to SG350** + all upstairs traffic |
| gi24 | 00:26:0A:45:AD:0C — Unknown |

### SG350 (192.168.1.250) — Upstairs/Office, 10-port

| Port | Devices |
|---|---|
| gi1 | **Uplink to 3650G** (bedroom) |
| gi3 | **Uplink to SG300** (basement) |
| gi4 | **.21 Deb's PC** |
| gi5 | TeensyMaestro (usually off) |
| gi7 | **.205 Fred's PC** |

### 3650G (Bedroom) — Big old Cisco, via SG350 gi1

Feeds: HDHomeRun, Arlo, UniFi AP, Roku, Amazon Echo, weather stations, living room/garage dumb switches

### SmartSDR Audio Path

```
Flex (.238) [SG300 gi5] → SG300 backplane → [SG300 gi12] uplink → [SG350 gi3] → SG350 backplane → [SG350 gi7] Fred's PC (.205)
```

Two switch hops, all gigabit. Single uplink (gi12↔gi3) carries ALL inter-floor traffic.

## SSH Access

- SG300: `ssh -oKexAlgorithms=+diffie-hellman-group1-sha1 -oHostKeyAlgorithms=+ssh-dss -oCiphers=+aes256-cbc -oMACs=+hmac-sha1 fred@192.168.1.251`
- SG350: `ssh -oKexAlgorithms=+diffie-hellman-group14-sha1 -oHostKeyAlgorithms=+ssh-rsa fred@192.168.1.250`

## 3650G Connections (from CDP + spanning-tree)

| 3650G Port | Role | State | Speed | Connects To |
|---|---|---|---|---|
| Gi0/1 | Root | FWD | 1Gbps | SG300 gi12 (primary uplink to basement) |
| Gi0/5 | Designated | FWD | 1Gbps | Linksys/AnFBIVan (.2), Living Room (.218) |
| Gi0/7 | Designated | FWD | 1Gbps | OpenMediaVault (.18), weewx2 (.236), Home Assistant (.14) |
| Gi0/11 | Designated | FWD | 1Gbps | ? (.77) |
| Gi0/12 | **Alternate** | **BLK** | 1Gbps | SG300 gi24 (BLOCKED backup — spanning tree) |
| Gi0/15 | Designated | FWD | **100Mbps** | Dumb switch (garage or living room) |
| Gi0/19 | Designated | FWD | **100Mbps** | Dumb switch (garage or living room) |
| Gi0/21 | Designated | FWD | 1Gbps | SG350 gi1 (uplink to office) |
| Gi0/24 | Designated | FWD | 1Gbps | Antenna switch (.189), Rokus, weather, IoT |

### 3650G Removal Plan (TODO)

The 3650G has 3 paths to the rest of the network:
1. Gi0/1 → SG300 gi12 (primary, forwarding)
2. Gi0/12 → SG300 gi24 (blocked by spanning tree)
3. Gi0/21 → SG350 gi1

**When removing the 3650G:**
- **DO NOT** just replace with a dumb switch connected to both SG300 and SG350 — no spanning tree = broadcast loop
- **Option A:** Single cable from dumb switch → SG300 (one uplink only, cleanest)
- **Option B:** Single cable from dumb switch → SG350 (keeps upstairs together, but adds hop for basement traffic)
- **Move Gi0/15 and Gi0/19 devices** (garage/living room 100Mbps dumb switches) directly to basement SG300 if cables reach
- **Relocate Gi0/24 devices** (Rokus, IoT, weather) to the replacement dumb switch
- **Gi0/5 devices** (Linksys, living room) can go to dumb switch or direct to SG300
- **Gi0/7 devices** (OMV, weewx, HA) should go to SG300 for proximity to Proxmox
- **Disconnect SG300 gi24** — no longer needed once 3650G backup path is gone
- **Key:** only ONE cable from the replacement dumb switch to ONE managed switch. No dual-homing without spanning tree.
- After 3650G is removed and no loops exist, disable spanning tree on SG350: `configure` → `no spanning-tree` → `exit` → `write memory`
- SG350 features already disabled (2026-03-15): IGMP snooping, LLDP, CDP — CPU dropped from 10% to 2%

## Audio Dropout Investigation (2026-03-15)

- Both switches: zero port errors, zero drops, zero collisions
- Ping Flex→PC: <1ms, 0% loss
- SG350 CPU: 10% (not overloaded)
- Fred's PC: 8% CPU, 19/32GB RAM, Realtek 2.5GbE at 1Gbps
- Hyper-V removed (had virtual switch on physical NIC)
- NIC settings: EEE off, Power Saving off, Interrupt Moderation off, SelectiveSuspend off
- Flow Control: Rx & Tx Enabled (reverting to disabled made things worse)
- **Suspect:** Realtek 2.5GbE NIC on Fred's PC — consider replacing with Intel gigabit adapter ($15 USB or PCIe)
- SG300 multicast filtering: DISABLED — all broadcast/multicast floods all ports. Not critical (HPSDR is unicast) but could enable for cleaner traffic
- 3650G IGMP snooping: enabled and working
- Spanning tree: working correctly, 3650G Gi0/12→SG300 gi24 is blocked (backup path)
- **Conclusion:** Network is clean. Problem is likely the Realtek NIC or SmartSDR buffering.

## FlexRadio Network Recommendations (from helpdesk + community)
- Disable "Allow computer to turn off this device to save power" on NIC
- Disable Energy Efficient Ethernet (EEE) / Green Ethernet on NIC AND switch
- FlexRadio recommends setting NIC speed to **100M Full Duplex** instead of Auto Negotiate (auto-negotiate can cause issues with real-time VITA-49 streaming)
- Audio dropouts originate from transport layer, not the radio itself
- UDP packet loss from routers/switches causes dropouts
- Realtek NICs are known to be problematic — Intel NICs are preferred for SmartSDR
- SmartSDR uses VITA-49 protocol for audio/data — very sensitive to jitter
- Fred's PC NIC settings that work: EEE off, Power Saving off, Interrupt Moderation off, SelectiveSuspend off, Flow Control Rx & Tx Enabled
- **DO NOT** disable Flow Control on Realtek 2.5GbE — made things significantly worse
- The whole reason for managed switches was to support SmartSDR remote operation from upstairs
