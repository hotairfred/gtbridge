# Home Network Consolidation Plan

## Current Setup

| Machine | Hardware | Role | Storage Used | Status |
|---------|----------|------|-------------|--------|
| G5 Mini | HP EliteDesk G5 Mini | Proxmox — Plex server, UniFi controller, other containers | Local SSD | **Keep** |
| Fileserver | i7-4770, Proxmox + OMV | File storage (SMB) | 1.5 TB of 3 TB | **Retire** |
| Media box | i5 (same vintage) | SMB share for Plex media | ~1 TB | **Retire** |

**Networking:** Mikrotik router, Cisco SG300 24-port core switch, SG350 upstairs office switch, UniFi APs

## Goal

Consolidate the i7-4770 and i5 machines into a single NAS appliance. Keep the G5 Mini as-is for compute (Plex app, UniFi, containers). Also serve as offsite backup target for the Apex office app via Tailscale.

## Recommended: 2-Bay NAS + Mirrored Drives

### Why Not the Ubiquiti UNAS Pro
- Looks awesome. 7 bays in 2U. Very tempting.
- But 7 bays to fill 2 of them is overkill for 2.5 TB of current data.
- $500+ before drives. Ubiquiti NAS software is still young compared to Synology DSM or TrueNAS.
- Save the money unless you actually need 7 bays someday.

### NAS Options

**Option A: Synology DS224+ (~$300)**
- Best "set and forget" NAS software (DSM)
- Great backup/sync tools, Plex package, Docker support
- Caveat: Synology is pushing Synology-branded drives (nag warnings on third-party). Subscription creep on some features. Hardware is overpriced for the specs. Community sentiment has soured somewhat.

**Option B: TrueNAS on cheap mini PC (~$100-150 hardware)**
- Free, open-source, ZFS-native (best filesystem for data integrity)
- More hands-on to set up but more flexible
- Could run on another G5 Mini or similar

**Option C: Just add storage to existing G5 Mini**
- Internal 2.5" SATA if there's a second slot, or USB-C DAS enclosure
- Cheapest option but USB reliability on Proxmox is questionable for automated backups
- Internal SATA is fine if the slot exists

### Recommended Drives (as of March 2026)

Sweet spot is **16-20TB** at roughly **$13-16/TB**.

| Drive | Capacity | Approx Price | Notes |
|-------|----------|-------------|-------|
| Seagate Exos X18/X20 | 18-20 TB | ~$230-320 | Enterprise grade, 5-year warranty, often cheaper per TB than consumer NAS drives. Data center workhorses. |
| Toshiba N300 | 16-18 TB | ~$210-290 | 10-20% cheaper than IronWolf/Red Plus. Underrated, same core specs. |
| Seagate IronWolf | 16-18 TB | ~$250-310 | The "standard" NAS drive. Reliable, well-supported, slight price premium. |
| WD Red Plus | 16-18 TB | Availability issues | WD reportedly sold out for most of 2026. Prices inflated where available. Skip for now. |

**Recommendation:** Two 16TB Seagate Exos or Toshiba N300 in mirror. ~$400-450 total for 16TB usable. That's 6x current usage with years of room for Plex growth.

## Consolidation Steps

1. Buy NAS appliance (or repurpose hardware) + two matched drives
2. Set up RAID 1 (mirror) — protects against single drive failure
3. Migrate 1.5 TB from OMV fileserver to NAS
4. Migrate 1 TB Plex media from i5 box to NAS
5. Point G5 Mini Plex container at NAS share for media library
6. Set up Tailscale on NAS for offsite backup from Apex office
7. Configure nightly backup cron: office `pg_dump` + media sync to NAS
8. Verify backups are landing for a week
9. Power off i7-4770 and i5, enjoy lower electric bill

## Offsite Backup Role (Apex Office)

- Receives nightly `pg_dump` from office G5 Mini over Tailscale tunnel
- Optionally receives media file sync (uploaded documents, field photos)
- Database dumps are tiny (few MB) — negligible storage impact
- Tailscale makes the NAS appear as a local device to the office server, no port forwarding needed

## Power Savings

| Machine | Est. Idle Power | Annual Cost (~$0.12/kWh) |
|---------|----------------|--------------------------|
| i7-4770 (retire) | ~60-80W | ~$65-85/yr |
| i5 (retire) | ~50-70W | ~$55-75/yr |
| NAS replacement | ~15-25W | ~$16-27/yr |
| **Net savings** | | **~$75-130/yr** |

The NAS roughly pays for itself in electricity savings within 2-3 years, plus you get better reliability, less noise, and fewer machines to maintain.

## Decision Notes (Grayline + Fred, March 2026)

### Winner: Synology DS225+ (~$339) + 2x Seagate Exos X14 12TB (~$290 ea)

**Total: ~$919 all in for 12TB mirrored storage.**

### Why DS225+ over DS224+
- DS225+ has 2.5GbE on one port (vs 1GbE on 224+)
- Same price ballpark (~$339 vs ~$300)
- Lost hardware transcoding (no Quick Sync) — doesn't matter since Plex runs on the G5 Mini, NAS just serves files
- DSM 7.3 reversed the third-party drive lockout — no nag screens, full SMART monitoring on Seagate/WD/Toshiba drives

### Why 12TB over 16TB/20TB
- Current usage is 2.5TB — 12TB is nearly 5x headroom
- Plex library is watch-and-delete, not hoarding — won't grow dramatically
- 12TB Exos X14 at $290/ea vs 16TB X18 at $308/ea (when in stock) vs 20TB X20z at $352/ea
- Buy-once-cry-once still applies at 12TB — plenty of room
- 16TB drives had stock issues at time of research; 12TB and 20TB were available

### Why not TrueNAS / Beelink ME Pro
- Beelink ME Pro + drives comes out to roughly the same price (~$760+)
- More flexibility but more maintenance — another box to manage
- Already juggling pitaya, tower skimmer, GTBridge, work webapp, lot grading calc
- Synology is set-and-forget; save the tinkering energy for ham radio projects

### Why not keep the i7-4770 as a TrueNAS box
- Idles at 60-80W vs Synology at 15-25W
- $50-60/year difference in electricity just sitting there humming
- Whole point is consolidating and reducing power draw

### Drive source
- ServerPartDeals.com — Dell/Seagate Exos X14 ST12000NM0128 12TB SATA refurb
- Enterprise helium-sealed, CMR, 7200RPM, 256MB cache
- SATA 6Gb/s (confirmed — DS225+ is SATA only, no SAS)

### Prices may shift — revisit after Red Pitaya deployment.
