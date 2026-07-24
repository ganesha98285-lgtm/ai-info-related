"""Prime-time scheduling helper (multi-timezone).

Shorts are scheduled to the best posting windows for the channel's TWO main
markets:
  - USA (America/New_York): 4 shorts — 2 in the evening + 2 at night
  - India (Asia/Kolkata):   2 shorts — night, between 9:00-10:00 PM IST
Total = 6 shorts/day.

(A long-form vlog slot exists too, but long video is only added later once the
channel's reach grows — see SHORTS_ONLY in config.)

All slots are converted to UTC RFC3339 for the YouTube API `publishAt`.
"""
from __future__ import annotations

import datetime as dt

import pytz

from config import settings

# 6 daily short slots as (timezone, hour, minute), in publishing order.
SHORT_SLOTS = [
    (settings.usa_timezone, 18, 0),    # USA evening 1  (6:00 PM ET)
    (settings.usa_timezone, 20, 0),    # USA evening 2  (8:00 PM ET)
    (settings.usa_timezone, 22, 0),    # USA night 1    (10:00 PM ET)
    (settings.usa_timezone, 23, 30),   # USA night 2    (11:30 PM ET)
    (settings.india_timezone, 21, 0),  # India night 1  (9:00 PM IST)
    (settings.india_timezone, 21, 45), # India night 2  (9:45 PM IST)
]

# Long-form vlog slot — only used when long video is enabled later.
LONG_VLOG_SLOT = (settings.usa_timezone, 15, 0)  # 3:00 PM ET


def next_slot(zone_name: str, hour: int, minute: int,
              base: dt.datetime | None = None) -> dt.datetime:
    """Next occurrence of a local HH:MM in `zone_name` (today or tomorrow)."""
    zone = pytz.timezone(zone_name)
    now = base.astimezone(zone) if base else dt.datetime.now(zone)
    naive = dt.datetime(now.year, now.month, now.day, hour, minute)
    candidate = zone.localize(naive)
    if candidate <= now:
        candidate = zone.localize(naive + dt.timedelta(days=1))
    return candidate


def rfc3339(when: dt.datetime) -> str:
    """YouTube API wants UTC RFC3339 (e.g. 2026-07-24T19:00:00Z)."""
    return when.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def long_vlog_publish_time() -> dt.datetime:
    zone_name, hour, minute = LONG_VLOG_SLOT
    return next_slot(zone_name, hour, minute)


def shorts_publish_times(count: int) -> list[dt.datetime]:
    """Return `count` prime-time publish datetimes (cycles slots if needed)."""
    times: list[dt.datetime] = []
    for i in range(count):
        zone_name, hour, minute = SHORT_SLOTS[i % len(SHORT_SLOTS)]
        times.append(next_slot(zone_name, hour, minute))
    return times


if __name__ == "__main__":
    print("USA tz:", settings.usa_timezone, "| India tz:", settings.india_timezone)
    for i, t in enumerate(shorts_publish_times(settings.shorts_per_day), 1):
        print(f"Short {i} publish:", t, "->", rfc3339(t))
