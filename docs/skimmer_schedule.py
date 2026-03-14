"""
skimmer_schedule.py — Auto-update CWSL_DIGI day/night switching based on sunrise/sunset.

Calculates sunrise/sunset for grid EM79 (Middletown, OH), then updates
Windows scheduled tasks to switch CWSL_DIGI between day and night configs.

Run daily via Task Scheduler, or once at boot.

Usage: python skimmer_schedule.py [--dry-run]
"""

import subprocess
import sys
from datetime import datetime, timedelta

try:
    from astral import LocationInfo
    from astral.sun import sun
except ImportError:
    print("Install astral: pip install astral")
    sys.exit(1)

# Config
GRID = "EM79sm"
DAY_CONFIG = "day_ft8"
NIGHT_CONFIG = "night_ft8"
SWITCH_BAT = r"C:\CWSL_DIGI\switch_mode.bat"

# Offset: switch to day X minutes after sunrise, night X minutes after sunset
# Negative = before, positive = after
DAY_OFFSET_MIN = 30    # 30 min after sunrise (let bands open up)
NIGHT_OFFSET_MIN = 30  # 30 min after sunset (bands still closing)

DRY_RUN = "--dry-run" in sys.argv


def grid_to_latlon(grid: str) -> tuple:
    """Convert Maidenhead grid to lat/lon."""
    grid = grid.upper()
    lon = (ord(grid[0]) - ord('A')) * 20 - 180
    lat = (ord(grid[1]) - ord('A')) * 10 - 90
    lon += (int(grid[2]) * 2)
    lat += int(grid[3])
    if len(grid) >= 6:
        lon += (ord(grid[4]) - ord('A')) * (2 / 24) + (1 / 24)
        lat += (ord(grid[5]) - ord('A')) * (1 / 24) + (1 / 48)
    else:
        lon += 1
        lat += 0.5
    return lat, lon


def get_sun_times(lat: float, lon: float) -> tuple:
    """Get today's sunrise and sunset in UTC."""
    loc = LocationInfo(latitude=lat, longitude=lon)
    s = sun(loc.observer, date=datetime.now(tz=__import__('datetime').timezone.utc).date())
    return s["sunrise"], s["sunset"]


def update_task(task_name: str, utc_time: datetime, config: str):
    """Update a Windows scheduled task to run at the given UTC time."""
    # Convert UTC to local time (schtasks uses local time)
    local_time = utc_time.astimezone()
    time_str = local_time.strftime("%H:%M")
    utc_str = utc_time.strftime("%H:%M")
    bat_cmd = f"{SWITCH_BAT} {config}"

    print(f"  {task_name}: {utc_str} UTC ({time_str} local) -> {bat_cmd}")

    if not DRY_RUN:
        # Delete and recreate (schtasks /change requires password)
        subprocess.run(f'schtasks /delete /tn "{task_name}" /f',
                       shell=True, capture_output=True, text=True)
        result = subprocess.run(
            f'schtasks /create /tn "{task_name}" /tr "{bat_cmd}" /sc daily /st {time_str} /f',
            shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}")
        else:
            print(f"  OK")
    else:
        print(f"  (dry run)")


def main():
    lat, lon = grid_to_latlon(GRID)
    sunrise, sunset = get_sun_times(lat, lon)

    day_switch = sunrise + timedelta(minutes=DAY_OFFSET_MIN)
    night_switch = sunset + timedelta(minutes=NIGHT_OFFSET_MIN)

    print(f"Grid: {GRID} ({lat:.2f}, {lon:.2f})")
    print(f"Sunrise: {sunrise.strftime('%H:%M')} UTC")
    print(f"Sunset:  {sunset.strftime('%H:%M')} UTC")
    print(f"Day switch:   {day_switch.strftime('%H:%M')} UTC (+{DAY_OFFSET_MIN}min)")
    print(f"Night switch: {night_switch.strftime('%H:%M')} UTC (+{NIGHT_OFFSET_MIN}min)")
    print()

    update_task("SkimmerDay", day_switch, DAY_CONFIG)
    update_task("SkimmerNight", night_switch, NIGHT_CONFIG)

    print()
    print("Done. Tasks updated for today's sunrise/sunset.")


if __name__ == "__main__":
    main()
