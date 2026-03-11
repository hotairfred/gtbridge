# Cisco SG300 Setup for FlexRadio

Quick guide for configuring a Cisco SG300 managed switch for use with a FlexRadio. These settings resolved audio dropouts, packet loss, and CW latency issues on a Flex 6700 with multiple slices.

## Factory Reset (if needed)

Hold the recessed reset button (paperclip) while the switch is powered on until the lights flash. Release and wait for it to boot. Takes about a minute.

## Initial Access

- Default IP: `192.168.1.254`
- Default login: `cisco` / `cisco`
- It will force a password change on first login
- Access via browser: `https://192.168.1.254` (accept the self-signed cert warning)
- If you changed the password and lost track of the IP, the switch may grab a DHCP address — check your router's DHCP leases

## Step 1: Set a Static IP (optional)

If you want a fixed address instead of .254:

1. Go to **Administration > Management Interface > IPv4 Interface**
2. Set to **Static**
3. Enter your desired IP, subnet mask (255.255.255.0), and gateway
4. Save — you'll need to reconnect at the new IP

## Step 2: Disable Energy Efficient Ethernet (EEE)

This is the #1 cause of audio dropouts on Flex radios. EEE puts ports to sleep during low activity, causing micro-dropouts when they wake.

1. Go to **Port Management > Green Ethernet > Properties**
2. Uncheck **Energy Detect** and **Short Reach** globally, or:
3. Go to the **Port Settings** tab under Green Ethernet
4. Select **ALL** ports, click **Edit**
5. Set **802.3 Energy Efficient Ethernet** to **Disable**
6. Apply

## Step 3: Identify the Flex Port

Look at the MAC address table to find which port the Flex is on:

1. Go to **Status and Statistics > MAC Address Table**
2. Look for the Flex's MAC prefix: `04:D4:C4` (FlexRadio manufacturer prefix)
3. Note which port (e.g., GE9)

If you know the Flex's IP, you can also check by looking at which port shows a single MAC address matching the Flex.

## Step 4: Lock the Flex Port to 100M Full Duplex

Gigabit auto-negotiation can cause timing issues with the Flex, especially on boot. The radio only needs ~500 kbps per panadapter — 100 Mbps is more than enough.

1. Go to **Port Management > Port Settings**
2. Select the Flex's port
3. Click **Edit**
4. Set **Speed** to **100M**
5. Set **Duplex** to **Full**
6. Apply

## Step 5: Disable Flow Control on the Flex Port

Flow control can cause the switch to pause packet delivery, which creates audio glitches.

1. Still in **Port Management > Port Settings**
2. Select the Flex's port, click **Edit**
3. Set **Flow Control** to **Disable**
4. Apply

## Step 6: Leave MDI/MDIX on Auto

No change needed — Auto is the default and correct setting. The switch and Flex will negotiate the cable crossover automatically.

## Step 7: Save Configuration

**Important** — changes are running config only until you save:

1. Click the flashing **Save** icon (top of page), or
2. Go to **Administration > File Management > Copy/Save Configuration**
3. Copy **Running Configuration** to **Startup Configuration**

## Verification

After setup, check for packet loss:

1. Go to **Status and Statistics > Interface Statistics** (or **RMON > Statistics**)
2. Look at the Flex's port for:
   - **FCS Errors** — should be 0
   - **Dropped Packets** — should be very low (single digits out of tens of thousands is fine)
   - **Collisions** — should be 0 on full duplex

## What You DON'T Need to Change

- **STP (Spanning Tree)** — leave at default, not relevant for a simple home network
- **QoS** — not necessary for local Flex operation (matters more for SmartLink remote)
- **VLANs** — leave at default unless you have a specific reason
- **SSH/CLI** — the web UI handles everything above; the SG300 CLI is not standard IOS syntax

## PC-Side Settings (SmartSDR Computer)

On the PC running SmartSDR, check the network adapter settings:

1. Open **Device Manager > Network Adapters > [your adapter] > Properties**
2. **Advanced** tab:
   - Set **Interrupt Moderation** to **Disabled** (or rate to Off)
   - Set **Energy Efficient Ethernet** to **Disabled** (if present)
   - Maximize **Receive Buffers** and **Transmit Buffers** to highest available values
3. **Power Management** tab:
   - Uncheck **"Allow the computer to turn off this device to save power"**

## Results

After these changes on a Flex 6700 with multiple slices:
- Packet loss dropped to < 0.01% (6 drops out of 62,500 packets)
- Bufferbloat grade: A (0.8ms unloaded jitter)
- Audio dropouts eliminated

## Why This Works

The Flex streams real-time audio and panadapter data via UDP. Unlike TCP, UDP doesn't retransmit dropped packets — if a packet is lost, you hear a glitch. EEE and auto-negotiation introduce micro-delays that are invisible to web browsing but fatal to real-time audio. Locking the port speed and disabling power-saving features gives the Flex a clean, predictable link.

## Reference

- [FlexRadio Community: Network optimization threads](https://community.flexradio.com)
- [FlexRadio Helpdesk: Optimizing Ethernet Adapter Settings](https://helpdesk.flexradio.com/hc/en-us/articles/202118518)
