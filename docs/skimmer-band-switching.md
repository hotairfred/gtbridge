# Skimmer Band Switching Plan

Red Pitaya 125-14 does 8 bands max via SkimSrv. Use time-of-day switching
to cover all HF bands including 60m by swapping SkimSrv profiles around
sunrise/sunset.

## Band Profiles

### Daytime (after sunrise)
Focus on high bands where propagation exists during daylight.

| Slot | Band | Center (kHz) | Coverage at 192kHz |
|------|------|-------------|-------------------|
| 1 | 60m | 5357 | 5261 - 5453 |
| 2 | 30m | 10125 | 10029 - 10221 |
| 3 | 20m | 14100 | 14004 - 14196 |
| 4 | 17m | 18100 | 18004 - 18196 |
| 5 | 15m | 21100 | 21004 - 21196 |
| 6 | 12m | 24940 | 24844 - 25036 |
| 7 | 10m | 28100 | 28004 - 28196 |
| 8 | 10m beacon | 28200 | 28104 - 28296 |

Note: Could merge 10m + beacon into one slice if center freq covers both.
28150 center would cover 28054-28246, getting CW + beacons in one slot.
That frees a slot for 6m (50100) if we want it.

### Nighttime (before sunset)
Focus on low bands where propagation peaks after dark.

| Slot | Band | Center (kHz) | Coverage at 192kHz |
|------|------|-------------|-------------------|
| 1 | 160m | 1900 | 1804 - 1996 |
| 2 | 80m | 3600 | 3504 - 3696 |
| 3 | 60m | 5357 | 5261 - 5453 |
| 4 | 40m | 7100 | 7004 - 7196 |
| 5 | 30m | 10125 | 10029 - 10221 |
| 6 | 20m | 14100 | 14004 - 14196 |
| 7 | 17m | 18100 | 18004 - 18196 |
| 8 | 15m | 21100 | 21004 - 21196 |

### Overlap bands
60m, 30m, 20m, 17m, 15m are in both profiles -- no gap during transitions.

## Switching Strategy

### Simple: Two switches per day
- **Sunrise + ~30min:** Switch to daytime profile (drop 160/80/40, add 12/10/beacon)
- **Sunset - ~30min:** Switch to nighttime profile (drop 12/10/beacon, add 160/80/40)

### Better: Three switches per day
- **Sunrise + 30min:** Kill 160m (truly dead), add 10m
- **Midday:** Full daytime profile
- **Sunset - 30min:** Full nighttime profile

### Best: Data-driven
- Analyze existing RBN spot data to find actual peak activity windows per band
- Build a schedule based on real spot volume, not just sunrise/sunset
- Could query RBN raw data files to find when spots per band peak/die
- Grayline can crunch this -- download a week of raw RBN CSVs and histogram
  spot counts by band and hour-of-day for our grid square / CQ zone 4

## Implementation

SkimSrv stores band selection in `SkimSrv.ini`:
```
SegmentSel192=1111111100  (10 chars, one per band slot: 160 80 60 40 30 20 17 15 12 10)
```

### Option A: Swap INI files
1. Create `SkimSrv_day.ini` and `SkimSrv_night.ini` with different SegmentSel
2. Task Scheduler (Windows) or cron via Tailscale SSH:
   - Stop SkimSrv service
   - Copy appropriate INI over `SkimSrv.ini`
   - Start SkimSrv service
3. Calculate sunrise/sunset for tower lat/lon, adjust by offset

### Option B: Edit INI in place
1. Python script on the EliteDesk (or remotely via Tailscale)
2. Modify just the SegmentSel192 line
3. Restart SkimSrv
4. Sunrise/sunset calc via `datetime` + simple formula (no external deps)

### Option C: GTBridge integration
1. New module `skimmer_scheduler.py` that runs on this container
2. SSHs into the EliteDesk via Tailscale to swap configs
3. Uses actual sunrise/sunset for tower coordinates
4. Logs band switches
5. Could eventually use RBN spot analysis to optimize timing

## Tower Site Details
- Location: ~16.3 miles SW of WF8Z QTH
- Grid: EM79PI (from KA8ABR 10 GHz beacon)
- Coordinates: 39.359987°N, 84.692292°W
- EliteDesk G3 (i5-7600, 16GB) running SkimSrv + CWSL_DIGI
- Red Pitaya 125-14 on gigabit ethernet
- Tailscale for remote management
- Callsign: W8SLL-2

## Notes
- 14-bit Red Pitaya is fine for skimming -- HL2 is 12-bit and decoded CW
  just fine. Dynamic range only matters near strong local transmitters,
  and this is a receive-only site with no co-located TX.
- N6TV recommends 16-bit 122.16 ($739) but that's overkill for a quiet
  rural tower site. The 125-14 ($400) is widely used for RBN nodes.
- Contest weekends: consider locking to all-band mode (skip switching)
  and just run the 8 most active contest bands.
- RTTY skimming may be too CPU-heavy for the i5-7600 -- test first.
  CW + FT8/FT4 should be fine.
