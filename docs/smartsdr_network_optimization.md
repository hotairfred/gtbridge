# SmartSDR Network Optimization Reference

Compiled 2026-03-15. Flex 6700 on local LAN with two managed switches (SG300 + SG350) between radio and shack PC (Realtek 2.5GbE NIC). Intermittent audio dropouts.

---

## Table of Contents

1. [Understanding the Problem](#1-understanding-the-problem)
2. [NIC Configuration (Realtek RTL8125 2.5GbE)](#2-nic-configuration-realtek-rtl8125-25gbe)
3. [Intel vs Realtek NICs](#3-intel-vs-realtek-nics)
4. [Windows OS-Level Network Tuning](#4-windows-os-level-network-tuning)
5. [Windows Power Management](#5-windows-power-management)
6. [SmartSDR Application Settings](#6-smartsdr-application-settings)
7. [Switch Configuration (Cisco SG300 / SG350)](#7-switch-configuration-cisco-sg300--sg350)
8. [VITA-49 Protocol Characteristics](#8-vita-49-protocol-characteristics)
9. [Diagnostics and Testing](#9-diagnostics-and-testing)
10. [Windows Firewall](#10-windows-firewall)
11. [Known Realtek RTL8125 Issues](#11-known-realtek-rtl8125-issues)
12. [Nuclear Option: Replace the NIC](#12-nuclear-option-replace-the-nic)
13. [Quick Checklist](#13-quick-checklist)

---

## 1. Understanding the Problem

SmartSDR streams RX audio, metering, and display data (panadapter/waterfall) from the radio to the PC using **VITA-49 over UDP**. UDP has no retransmission -- when packets arrive late, out of order, or are dropped, you hear them immediately as pops, crackles, or audio dropouts. SmartSDR cannot buffer RX audio without destroying real-time operation.

**What matters is NOT bandwidth, but:**
- **Jitter** (variation in packet arrival time) -- must be < 10 ms, ideally < 5 ms
- **Packet loss** -- must be 0%; < 0.5% is "tolerable" but audible
- **DPC latency** on the PC -- the Windows kernel must process incoming UDP packets within ~2000 us

A single panadapter at 25 FPS + waterfall consumes only ~1.2 Mbps. A DAX audio channel adds another ~1.5 Mbps equivalent. Total bandwidth is trivial. The problem is always latency, jitter, or packet processing delays.

### Common Culprits (Local LAN)
- NIC interrupt coalescing / moderation holding packets too long
- NIC power management or EEE putting the link to sleep
- Switch EEE / Green Ethernet causing link renegotiation micro-delays
- Switch flow control pausing the port during bursts from other traffic
- Windows MMCSS network throttling (10,000 pkt/sec cap during multimedia)
- High DPC latency from NIC driver, antivirus, or other kernel drivers
- SG350 CPU overload from heavy traffic on other ports (known issue with gaming traffic)

---

## 2. NIC Configuration (Realtek RTL8125 2.5GbE)

All settings via: **Device Manager > Network adapters > Realtek > Properties > Advanced tab**

Or via PowerShell:
```powershell
# List all advanced properties and current values
Get-NetAdapterAdvancedProperty -Name "Ethernet" | Format-Table -AutoSize

# Set a specific property
Set-NetAdapterAdvancedProperty -Name "Ethernet" -RegistryKeyword "*InterruptModeration" -RegistryValue 0
```

### Critical Settings

| Setting | Recommended Value | Why |
|---------|------------------|-----|
| **Interrupt Moderation** | **Disabled** | FlexRadio official recommendation. Coalescing holds packets to reduce CPU interrupts, adding latency. For real-time UDP, you want every packet delivered immediately. |
| **Interrupt Moderation Rate** | **OFF** (if separate setting) | Same as above. |
| **Flow Control** | **Disabled** | FlexRadio official recommendation. TCP has its own flow control; for UDP, flow control pauses cause packet loss. |
| **Energy Efficient Ethernet (EEE)** | **Disabled** | FlexRadio official recommendation. EEE puts the PHY into low-power states during idle periods, causing micro-delays on wake-up that destroy real-time audio. Disable on BOTH NIC and switch. |
| **Green Ethernet** | **Disabled** | Same rationale as EEE. |
| **Receive Buffers** | **512** or higher (max available) | Larger buffers absorb burst traffic without dropping. FlexRadio recommends 256; for 2.5GbE, go higher. |
| **Transmit Buffers** | **512** or higher (max available) | Same rationale. |
| **Receive Side Scaling (RSS)** | **Enabled, 4 queues** | FlexRadio recommends RSS enabled with queue count = 4 for multi-core packet distribution. |
| **Large Send Offload v2 (IPv4)** | **Disabled** | FlexRadio recommends all offload features OFF. |
| **Large Send Offload v2 (IPv6)** | **Disabled** | Same. |
| **TCP Checksum Offload (IPv4)** | **Disabled** | Same. |
| **UDP Checksum Offload (IPv4)** | **Disabled** | Same. |
| **TCP Checksum Offload (IPv6)** | **Disabled** | Same. |
| **UDP Checksum Offload (IPv6)** | **Disabled** | Same. |
| **IPv4 Checksum Offload** | **Disabled** | Same. |
| **Speed & Duplex** | **Auto Negotiation** | Let the NIC and switch negotiate. If problems persist, try forcing 1.0 Gbps Full Duplex to avoid 2.5G negotiation issues. |
| **Wake on Magic Packet** | **Disabled** | Unnecessary; can cause spurious wakes. |
| **Wake on Pattern Match** | **Disabled** | Same. |
| **Power Saving Mode** | **Disabled** | Prevent the NIC from entering low-power states. |

### Power Management Tab

Device Manager > Realtek NIC > Properties > **Power Management** tab:
- **UNCHECK** "Allow the computer to turn off this device to save power"
- **UNCHECK** "Allow this device to wake the computer" (unless needed for WoL)

### PowerShell Bulk Configuration
```powershell
$nic = "Ethernet"  # Adjust to your adapter name

# Disable interrupt moderation
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*InterruptModeration" -RegistryValue 0

# Disable flow control
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*FlowControl" -RegistryValue 0

# Disable EEE
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*EEE" -RegistryValue 0

# Disable Large Send Offload
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*LsoV2IPv4" -RegistryValue 0
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*LsoV2IPv6" -RegistryValue 0

# Disable checksum offload
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*TCPChecksumOffloadIPv4" -RegistryValue 0
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*UDPChecksumOffloadIPv4" -RegistryValue 0
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*TCPChecksumOffloadIPv6" -RegistryValue 0
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*UDPChecksumOffloadIPv6" -RegistryValue 0
Set-NetAdapterAdvancedProperty -Name $nic -RegistryKeyword "*IPChecksumOffloadIPv4" -RegistryValue 0

# Disable power management
Set-NetAdapterPowerManagement -Name $nic -ArpOffload Disabled -NSOffload Disabled -WakeOnMagicPacket Disabled -WakeOnPattern Disabled -DeviceSleepOnDisconnect Disabled

# Verify settings
Get-NetAdapterAdvancedProperty -Name $nic | Format-Table DisplayName, DisplayValue -AutoSize
```

**Note:** Registry keyword names vary between Realtek driver versions. Always use `Get-NetAdapterAdvancedProperty` first to see the exact keywords available on your system. Download NIC drivers from your **motherboard manufacturer**, not from Realtek directly (OEM drivers match your specific Device ID).

---

## 3. Intel vs Realtek NICs

The consensus across FlexRadio forums, networking forums, and professional audio communities:

| Aspect | Intel | Realtek |
|--------|-------|---------|
| CPU usage during transfers | ~8% of one core | ~19% of one core |
| Throughput | 5%+ better under load | Adequate for SmartSDR bandwidth |
| Driver stability | Excellent across all OSes | Historically problematic (NDIS resets, packet loss) |
| DPC latency | Generally low | RTL8125 specifically has elevated ndis.sys DPC |
| Interrupt moderation granularity | Fine-grained control (Adaptive/Off/Low/Medium/High) | Typically just On/Off |
| Real-time audio suitability | Preferred for pro audio (Dante, AES67) | "It works until it doesn't" |

**If the Realtek 2.5GbE continues causing problems after all tuning, consider:**
- Intel I225-V 2.5GbE PCIe card (~$30-40)
- Intel I210 or I350 Gigabit PCIe card (~$25-40) -- 1 Gbps is vastly more than SmartSDR needs

---

## 4. Windows OS-Level Network Tuning

### 4a. Disable MMCSS Network Throttling

Windows' Multimedia Class Scheduler Service (MMCSS) throttles network traffic to 10,000 packets/sec when multimedia apps are running. This cap can starve SmartSDR's UDP stream.

```
Registry: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile
Value: NetworkThrottlingIndex (DWORD)
Default: 0x0000000a (10)
Recommended: 0xFFFFFFFF (disabled)
```

**PowerShell (run as Administrator):**
```powershell
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile" `
    -Name "NetworkThrottlingIndex" -Value 0xFFFFFFFF -Type DWord
```

**Reboot required.**

### 4b. Disable Nagle's Algorithm (TCP_NODELAY)

Nagle's algorithm batches small TCP packets, adding up to 200-300 ms delay. While SmartSDR uses UDP for audio/display, the command channel is TCP (port 4992), and DAX uses TCP as well. Disabling Nagle reduces control latency.

**Find your NIC's interface GUID:**
```powershell
Get-NetAdapter | Select-Object Name, InterfaceGuid
```

**Then set these values under the matching interface:**
```
Registry: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{YOUR-GUID}

TcpAckFrequency (DWORD) = 1     # Disable delayed ACK
TcpNoDelay (DWORD) = 1          # Disable Nagle
```

**PowerShell:**
```powershell
$guid = (Get-NetAdapter -Name "Ethernet").InterfaceGuid
$path = "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\$guid"
New-ItemProperty -Path $path -Name "TcpAckFrequency" -Value 1 -PropertyType DWord -Force
New-ItemProperty -Path $path -Name "TcpNoDelay" -Value 1 -PropertyType DWord -Force
```

**Reboot required.**

### 4c. Disable Network Task Offloading (Global)

```powershell
# Disable global task offloading at the OS level
netsh int tcp set global chimney=disabled
netsh int tcp set global autotuninglevel=disabled
netsh int tcp set global rss=enabled
netsh int tcp set global timestamps=disabled
```

**Note:** RSS should remain enabled (FlexRadio recommends it). The others can add latency.

### 4d. SystemProfile Settings

Additional MMCSS tuning in the same registry area:

```
Registry: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile

SystemResponsiveness (DWORD) = 0     # Default is 20 (%). Set to 0 to give max priority to multimedia tasks.
```

```powershell
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile" `
    -Name "SystemResponsiveness" -Value 0 -Type DWord
```

---

## 5. Windows Power Management

### 5a. Power Plan

```powershell
# List available power plans
powercfg /list

# Set to High Performance
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

# Or enable Ultimate Performance (hidden by default)
powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61
powercfg /setactive e9a42b02-d5df-448d-aa00-03f14749eb61
```

### 5b. Disable USB Selective Suspend

(Relevant if any USB audio devices or USB-Ethernet adapters are in the chain)

```powershell
# In current power plan, disable USB selective suspend
powercfg /SETACVALUEINDEX SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /SETACTIVE SCHEME_CURRENT
```

### 5c. Disable PCI Express Link State Power Management

```powershell
powercfg /SETACVALUEINDEX SCHEME_CURRENT 501a4d13-42af-4429-9fd1-a8218c268e20 ee12f906-d277-404b-b6da-e5fa1a576df5 0
powercfg /SETACTIVE SCHEME_CURRENT
```

### 5d. Processor Performance

```powershell
# Set minimum processor state to 100% (prevent frequency scaling)
powercfg /SETACVALUEINDEX SCHEME_CURRENT 54533251-82be-4824-96c1-47b60b740d00 893dee8e-2bef-41e0-89c6-b55d0929964c 100
powercfg /SETACTIVE SCHEME_CURRENT
```

---

## 6. SmartSDR Application Settings

### 6a. Display Settings (Reduce Network Load)

Each open panadapter generates VITA-49 UDP traffic proportional to its width and frame rate:

| Setting | Bandwidth Impact |
|---------|-----------------|
| 1 pan @ 25 FPS, 1500px wide | ~500 kbps |
| 1 pan @ 5 FPS, 1500px wide | ~100 kbps |
| Waterfall @ rate 80 | ~650 kbps |
| DAX audio channel | ~equivalent to max FPS+waterfall |
| 1 slice, FPS+Rate at 100% | ~1.6 Mbps upload from radio |

**To reduce load while troubleshooting:**
- Lower **Display > FPS** to 10-15 (or 5 for testing)
- Lower **Display > RATE** to 50 or below
- Reduce SmartSDR window width (directly reduces VITA-49 packet payload)
- Close unused panadapters/slices -- each one doubles traffic
- Turn waterfall OFF *and* set rate to 0 (it still sends data even when "off" unless rate is 0)

### 6b. DAX Settings

- In Windows Sound Control Panel, set DAX Audio devices to **16-bit, 48000 Hz**
- DAX buffer size trades latency for reliability:
  - Smaller buffers = lower latency, more susceptible to dropouts
  - Larger buffers = more latency, more resilient
  - For local LAN, default should be fine; increase only if experiencing dropouts

### 6c. Low Bandwidth Connection Mode

SmartSDR v2.0+ has a "Low Bandwidth connection" option that forces:
- Single Pan & Slice
- FPS = 5
- Waterfall Rate = 60

Useful for isolating whether display traffic is contributing to audio dropouts.

### 6d. Digital Mode Filter

If using digital modes (FT8/WSJT-X): set to **Low Latency** in the slice settings. But do **NOT** check "Low Latency Filters for Digital Modes" if using WSJT-X modes.

---

## 7. Switch Configuration (Cisco SG300 / SG350)

### 7a. Disable EEE / Green Ethernet (CRITICAL)

EEE is **incompatible with real-time applications**. It puts physical links into low-power states during idle periods, causing micro-second to millisecond wake-up delays. Even Cisco acknowledges this for Dante audio.

**Web Interface (SG300/SG350):**
1. Navigate to **Port Management > Green Ethernet > Properties**
2. **Uncheck** "802.3 Energy Efficient Ethernet (EEE)"
3. Click **Apply**
4. Navigate to **Port Management > Green Ethernet > Port Settings**
5. For the Flex radio port and PC port: set **EEE** to **Disabled**, **Short Reach** to **Disabled**
6. Click **Apply**
7. **Save** running config to startup config

**CLI:**
```
configure terminal
no green-ethernet eee
interface gi1      # Replace with your port numbers
no green-ethernet eee
exit
interface gi2
no green-ethernet eee
exit
copy running-config startup-config
```

### 7b. Disable Flow Control on Switch Ports

Flow control (802.3x PAUSE frames) can cause the switch to tell the radio to stop sending, dropping real-time UDP data.

**Web Interface:**
1. **Port Management > Port Settings**
2. For ports connected to Flex and PC: set **Flow Control** to **Disabled**
3. Click **Apply**, save config

**CLI:**
```
configure terminal
interface gi1
no flowcontrol
exit
copy running-config startup-config
```

### 7c. QoS Configuration

Option 1: **Port-based priority** (simplest):
1. **Quality of Service > General > QoS Properties** -- set QoS Mode to **Basic**
2. Set the Flex radio port and PC port to **Trust Mode: CoS** or **DSCP**
3. Set those ports to **highest CoS priority (7)** or map to queue 8

Option 2: **DSCP-based priority** (if other traffic needs QoS too):
1. Set QoS Mode to **Advanced**
2. Create an ACL matching UDP traffic from the Flex radio IP
3. Map it to DSCP EF (Expedited Forwarding, value 46)
4. Map DSCP EF to the highest priority queue (queue 8, Strict Priority)

**For the SG300, basic port-based priority is sufficient for a home network.**

### 7d. IGMP Snooping

IGMP snooping is relevant if you have multicast traffic (e.g., VITA-49 discovery uses broadcast/multicast on ports 4991/4992). On the SG300:

1. **Multicast > IGMP Snooping** -- ensure it's **Enabled** globally
2. This prevents multicast from flooding all ports (reducing load on uninvolved ports)
3. If the Flex is not being discovered, check that IGMP snooping isn't blocking the discovery multicast -- in that case, add the querier or disable snooping temporarily to test

### 7e. SG350 CPU Overload (Known Issue)

The SG350 CPU spikes to 50% under heavy traffic (e.g., gaming). This can cause the switch to delay or drop packets on ALL ports, including the path to the Flex.

**Mitigations:**
- Move the Flex and shack PC to the **SG300** (not the SG350) if possible
- Rate-limit non-critical ports on the SG350
- Consider replacing the SG350 with a switch that has better CPU headroom, or use an unmanaged switch for the Flex/PC segment

### 7f. Port Speed / Duplex

- Verify both the Flex port and PC port are negotiating at **1 Gbps Full Duplex** (check via switch port status page)
- If you see any half-duplex or 100 Mbps, there's a cable or connector issue
- The Flex 6700 has a Gigabit NIC; it should always link at 1 Gbps

### 7g. Cable Quality

- Use **Cat 5e or Cat 6** minimum between each device and switch
- Inspect RJ45 connectors for corrosion or bent pins
- Replace any cables longer than 5 years or that show physical damage
- Test with a known-good short cable directly between radio and PC to isolate switch issues

---

## 8. VITA-49 Protocol Characteristics

- **Transport:** UDP (no retransmission, no flow control)
- **Ports:** UDP 4991 (data streams), UDP 4992 (discovery), TCP 4992 (command/control)
- **Packet size:** Up to 1518 bytes (max Ethernet frame). Display data exceeds 1500-byte IP payload and relies on IP fragmentation/reassembly -- this is normal and expected
- **Streams:** Separate VITA-49 streams for audio, metering, panadapter FFT, waterfall
- **Packet counting:** Each VITA-49 packet has a sequence counter per stream; the client can detect drops when the count is non-sequential
- **MTU:** Standard 1500 is correct. Do NOT enable jumbo frames -- the radio doesn't use them
- **Fragmentation:** Switches and routers must NOT block fragmented UDP packets (some firewalls/routers do this by default)

**Network quality targets for reliable SmartSDR operation:**
| Metric | Acceptable | Ideal |
|--------|-----------|-------|
| Jitter | < 20 ms | < 5 ms |
| Packet loss | < 0.5% | 0% |
| Latency | < 50 ms | < 5 ms (LAN) |

---

## 9. Diagnostics and Testing

### 9a. iPerf3 Network Testing

FlexRadio recommends iPerf3 for validating network quality. Download from https://iperf.fr/iperf-download.php

**Run iPerf3 server on one machine, client on the other:**

```bash
# On machine A (server):
iperf3 -s

# On machine B (client):

# Test 1: TCP baseline
iperf3 -c <server_ip> -t 30

# Test 2: TCP reverse
iperf3 -c <server_ip> -R -t 30

# Test 3: UDP real-time simulation (THIS IS THE KEY TEST)
iperf3 -c <server_ip> -u -b 5M -t 30
# Target: 0% packet loss, < 10 ms jitter

# Test 4: UDP headroom
iperf3 -c <server_ip> -u -b 10M -t 30
# Marginal if this fails while Test 3 passes
```

### 9b. LatencyMon (DPC Latency)

Download from https://resplendence.com/latencymon

Run LatencyMon while SmartSDR is active. Look for:
- **All DPC/ISR routines < 2000 us** = suitable for real-time audio
- **2000-4000 us** = marginal, may cause dropouts
- **> 4000 us** = unsuitable, will cause dropouts

**Common offenders:**
- `ndis.sys` -- network driver (often Realtek). Fix: update driver, disable offloads, disable interrupt moderation
- `nvlddmkm.sys` -- NVIDIA GPU driver. Fix: update driver
- `tcpip.sys` -- Windows TCP/IP stack. Fix: disable offloads
- `Wdf01000.sys` -- Windows Driver Framework. Fix: update all drivers
- Antivirus packet inspection (AVG, Norton, Kaspersky). Fix: disable or exclude SmartSDR

### 9c. Ping Test for MTU

Verify path MTU between PC and radio:
```cmd
ping -f -l 1472 192.168.1.238
```
If this fails with "packet needs to be fragmented," something in the path has a sub-1500 MTU. (1472 + 28 bytes IP/ICMP header = 1500.)

### 9d. Continuous Ping for Dropout Correlation

Run a continuous ping while operating and listen for dropouts:
```cmd
ping -t 192.168.1.238 > ping_log.txt
```
Check the log for spikes or timeouts that correlate with audio dropouts.

### 9e. Wireshark

If all else fails, capture traffic on the PC NIC filtered to the radio's IP. Look for:
- VITA-49 sequence number gaps (dropped packets)
- Bursts of retransmitted TCP on port 4992
- PAUSE frames from the switch (flow control)
- Large gaps between packets (> 20 ms)

---

## 10. Windows Firewall

SmartSDR installation creates firewall rules, but they may be overly broad or get corrupted by updates.

**Verify or create explicit rules:**
```powershell
# Allow SmartSDR inbound UDP (VITA-49 streams)
New-NetFirewallRule -DisplayName "SmartSDR VITA-49 UDP" -Direction Inbound -Protocol UDP -LocalPort 4991,4992 -Action Allow

# Allow SmartSDR inbound TCP (command channel)
New-NetFirewallRule -DisplayName "SmartSDR Command TCP" -Direction Inbound -Protocol TCP -LocalPort 4992 -Action Allow

# Allow SmartSDR application (belt and suspenders)
New-NetFirewallRule -DisplayName "SmartSDR Application" -Direction Inbound -Program "C:\Program Files\FlexRadio Systems\SmartSDR v3.x\SmartSDR.exe" -Action Allow
```

Also ensure the radio's IP is not being filtered by any third-party firewall or antivirus packet inspection.

---

## 11. Known Realtek RTL8125 Issues

The RTL8125 (2.5GbE) has documented problems across multiple platforms:

1. **NDIS Reset / Link Drop:** Random link up/down events with packet loss. RTL8125 controllers on some motherboards exhibit sudden link drops under load. Manifests as brief network outages.

2. **High rx_missed / rx_mac_error counts:** Even after disabling EEE and adjusting ring buffers, some RTL8125 implementations show persistent packet loss.

3. **ndis.sys DPC Latency:** The Realtek driver is a frequent offender in LatencyMon, showing high DPC execution times that directly cause audio processing delays.

4. **Driver Version Sensitivity:** Different driver versions behave very differently. Always use the driver from your **motherboard manufacturer's support page**, not from Realtek or Windows Update. Test multiple versions if problems persist.

5. **2.5G Negotiation Issues:** When connected to a 1G switch port, the NIC must negotiate down. Some RTL8125 revisions handle this poorly. If you see intermittent disconnects, force the NIC to **1.0 Gbps Full Duplex** in the Advanced settings rather than relying on auto-negotiation.

**Specific workaround from MSI forums:**
- Disable EEE
- Disable Green Ethernet
- Disable Large Send Offload (v1 and v2)
- Increase receive/transmit buffers to maximum
- Update to latest motherboard-specific driver
- If problems persist, add a PCIe Intel NIC

---

## 12. Nuclear Option: Replace the NIC

If all software/registry tuning fails, the most reliable fix is bypassing the Realtek NIC entirely:

**Recommended PCIe cards (any will work, SmartSDR needs < 5 Mbps):**
- **Intel I225-V** -- 2.5GbE, ~$30-40, excellent driver support
- **Intel I210-T1** -- 1GbE, ~$25, server-grade reliability
- **Intel I350-T2** -- Dual 1GbE, ~$30-40, often available used

Install the card, disable the onboard Realtek in BIOS or Device Manager, and reconfigure SmartSDR to use the Intel adapter. Intel NICs have consistently low DPC latency and superior interrupt handling for real-time applications.

---

## 13. Quick Checklist

Apply these in order, testing after each group:

### Group 1: NIC Settings (Device Manager)
- [ ] Disable Interrupt Moderation
- [ ] Disable Flow Control
- [ ] Disable EEE / Energy Efficient Ethernet
- [ ] Disable Green Ethernet
- [ ] Disable all offload features (LSO, checksum offload)
- [ ] Set Receive/Transmit Buffers to 512+
- [ ] Set RSS queues to 4
- [ ] Uncheck "Allow computer to turn off this device" in Power Management tab
- [ ] Verify driver is from motherboard manufacturer, not Windows Update

### Group 2: Windows Registry (reboot after)
- [ ] NetworkThrottlingIndex = 0xFFFFFFFF
- [ ] SystemResponsiveness = 0
- [ ] TcpAckFrequency = 1
- [ ] TcpNoDelay = 1

### Group 3: Windows Power
- [ ] Set power plan to High Performance or Ultimate Performance
- [ ] Disable PCI Express Link State Power Management

### Group 4: Switch Settings (SG300 + SG350)
- [ ] Disable EEE / Green Ethernet globally and per-port
- [ ] Disable Flow Control on Flex and PC ports
- [ ] Set QoS priority high on Flex and PC ports
- [ ] Verify ports negotiating at 1 Gbps Full Duplex
- [ ] Verify Flex and PC are on SG300 (not SG350 with CPU issue)

### Group 5: SmartSDR Settings
- [ ] Lower FPS to 15, Rate to 50 as a test
- [ ] Close unused panadapters/slices
- [ ] Verify DAX at 16-bit 48000 Hz

### Group 6: Diagnostics
- [ ] Run LatencyMon -- all DPC < 2000 us?
- [ ] Run iPerf3 UDP test -- 0% loss, < 10 ms jitter?
- [ ] Check for antivirus packet inspection
- [ ] Test direct cable from PC to radio (bypass switches) as isolation test

### Group 7: If All Else Fails
- [ ] Force NIC to 1.0 Gbps Full Duplex (avoid 2.5G negotiation)
- [ ] Install Intel PCIe NIC, disable Realtek
- [ ] Move Flex and PC to same switch (eliminate one hop)
- [ ] Replace cable between switches

---

## Sources

- [FlexRadio: Optimizing Ethernet Adapter Settings](https://helpdesk.flexradio.com/hc/en-us/articles/202118518-Optimizing-Ethernet-Adapter-Settings-for-Maximum-Performance)
- [FlexRadio: How to Reduce Network Bandwidth](https://helpdesk.flexradio.com/hc/en-us/articles/203891569-How-to-Reduce-Network-Bandwidth-utilized-by-SmartSDR)
- [FlexRadio Community: How do I fix choppy RX audio?](https://community.flexradio.com/discussion/8027646/how-do-i-fix-choppy-rx-audio)
- [FlexRadio Community: What causes SmartSDR to run choppy?](https://community.flexradio.com/discussion/7340346/how-do-i-determine-what-is-causing-smartsdr-to-run-choppy)
- [FlexRadio Community: Testing your Network Performance](https://community.flexradio.com/discussion/8033111/testing-your-network-performance)
- [FlexRadio Community: Audio dropouts using SmartLINK](https://community.flexradio.com/discussion/8033208/many-audio-dropouts-using-smartlink-4-1-15)
- [FlexRadio Community: Popping and crackling SmartSDR 4.1.5](https://community.flexradio.com/discussion/8033069/popping-and-crackling-smartsdr-4-1-5-on-any-remote-connection-not-hardwired)
- [FlexRadio Community: Audio stuttering in remote setup](https://community.flexradio.com/discussion/8030322/seeking-advice-resolving-audio-stuttering-in-remote-flexradio-setup)
- [FlexRadio Community: Helpful Network tips](https://community.flexradio.com/flexradio/topics/helpful-network-tips-and-ideas)
- [FlexRadio Community: VITA-49 fragmented packets](https://community.flexradio.com/discussion/7570910/fragmented-packets-and-packet-size)
- [FlexRadio Community: Display FPS bandwidth impact](https://community.flexradio.com/discussion/6485506/does-lowering-display-fps-or-waterfall-rate-reduce-network-bandwidth)
- [FlexRadio Community: DAX Audio over SmartLink choppy](https://community.flexradio.com/discussion/8033255/dax-audio-over-smartlink-choppy)
- [MSI Forums: RTL8125 packet loss fix](https://forum-en.msi.com/index.php?threads/fix-rtl8125-packet-loss-drop-outs-lags-general-failure.406338/)
- [ASRock Forums: RTL8125 NDIS Reset Problem](https://forum.asrock.com/forum_posts.asp?TID=14888&title=realtek-2-5gbe-rtl8125-ndis-reset-problem)
- [Cisco: Configure Green Ethernet on SG300](https://www.cisco.com/c/en/us/support/docs/smb/switches/cisco-small-business-300-series-managed-switches/smb5544-configure-global-green-ethernet-properties-on-a-switch-throu.pdf)
- [Cisco: QoS Advanced Mode on SG300](https://www.cisco.com/c/en/us/support/docs/smb/switches/cisco-small-business-300-series-managed-switches/smb64-qos-advanced-mode-configuration-on-300-series-managed-switch.html)
- [Resplendence: LatencyMon](https://resplendence.com/latencymon)
- [Microsoft: Power management on network adapter](https://learn.microsoft.com/en-us/troubleshoot/windows-client/networking/power-management-on-network-adapter)
- [Windows Forum: NetworkThrottlingIndex tuning](https://windowsforum.com/threads/tuning-networkthrottlingindex-for-better-windows-network-throughput.403836/)
