"""Publishing schedule — two US windows only: MORNING and EVENING.

Data-backed US engagement windows for short-form: the morning commute
(≈6-9 AM) and evening leisure time (≈6-9 PM), local time.
So we publish 5 shorts in each window, staggered 45 minutes apart:

  MORNING (America/New_York): 6:00, 6:45, 7:30, 8:15, 9:00 AM
  EVENING (America/New_York): 6:00, 6:45, 7:30, 8:15, 9:00 PM

Times are converted to UTC RFC3339 for the YouTube API's `publishAt`, so
YouTube itself releases each Short at the right moment.
"""
from __future__ import annotations

import datetime as dt

import pytz

from config import settings

MORNING_SLOTS = [(6, 0), (6, 45), (7, 30), (8, 15), (9, 0)]
EVENING_SLOTS = [(18, 0), (18, 45), (19, 30), (20, 15), (21, 0)]

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
    """First half of the batch -> morning window, second half -> evening window."""
    half = (count + 1) // 2
    times: list[dt.datetime] = []
    for i in range(count):
        if i < half:
            hh, mm = MORNING_SLOTS[i % len(MORNING_SLOTS)]
        else:
            hh, mm = EVENING_SLOTS[(i - half) % len(EVENING_SLOTS)]
        times.append(next_slot(hh, mm))
    return times


if __name__ == "__main__":
    print("US timezone:", settings.usa_timezone)
    for i, t in enumerate(shorts_publish_times(settings.shorts_per_day), 1):
        print(f"Short {i:2}: {t.strftime('%a %I:%M %p %Z')}  ->  {rfc3339(t)}")
