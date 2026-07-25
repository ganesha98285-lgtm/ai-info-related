"""Publishing schedule — US EVENING → LATE NIGHT only (no morning posts).

Short-form engagement peaks after work and stays strong late into the night, so
all 6 daily Shorts are spread across that window in America/New_York local time:

  6:00 PM · 7:30 PM · 9:00 PM · 10:15 PM · 11:30 PM · 12:45 AM

Times are converted to UTC RFC3339 for the YouTube API's `publishAt`, so
YouTube itself releases each Short at the right moment.
"""
from __future__ import annotations

import datetime as dt

import pytz

from config import settings

# Evening → late-night slots (local US time). Order = publishing order.
EVENING_SLOTS = [
    (18, 0),    # 6:00 PM  — after work
    (19, 30),   # 7:30 PM  — prime leisure
    (21, 0),    # 9:00 PM  — peak scrolling
    (22, 15),   # 10:15 PM — wind-down
    (23, 30),   # 11:30 PM — late night
    (0, 45),    # 12:45 AM — night owls
]

# Long-form slot (only used if long video is ever enabled).
LONG_VLOG_SLOT = (15, 0)


def _zone():
    return pytz.timezone(settings.usa_timezone)


def next_slot(hour: int, minute: int, base: dt.datetime | None = None) -> dt.datetime:
    """Next occurrence of a local HH:MM in the US timezone (today or tomorrow)."""
    zone = _zone()
    now = base.astimezone(zone) if base else dt.datetime.now(zone)
    naive = dt.datetime(now.year, now.month, now.day, hour, minute)
    candidate = zone.localize(naive)
    if candidate <= now + dt.timedelta(minutes=5):  # need a small buffer
        candidate = zone.localize(naive + dt.timedelta(days=1))
    return candidate


def rfc3339(when: dt.datetime) -> str:
    """YouTube API wants UTC RFC3339 (e.g. 2026-07-25T22:00:00Z)."""
    return when.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def long_vlog_publish_time() -> dt.datetime:
    return next_slot(*LONG_VLOG_SLOT)


def shorts_publish_times(count: int) -> list[dt.datetime]:
    """Evening → late-night slots, in order (cycles if count > slot count)."""
    times: list[dt.datetime] = []
    for i in range(count):
        hh, mm = EVENING_SLOTS[i % len(EVENING_SLOTS)]
        times.append(next_slot(hh, mm))
    return sorted(times)


if __name__ == "__main__":
    print("US timezone:", settings.usa_timezone, "(evening → late night only)")
    for i, t in enumerate(shorts_publish_times(settings.shorts_per_day), 1):
        print(f"Short {i:2}: {t.strftime('%a %I:%M %p %Z')}  ->  {rfc3339(t)}")
