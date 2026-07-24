"""US peak-time helper.

Best-performing posting windows (US audience, general consensus for
cute/animation/ASMR lifestyle content). Times are LOCAL to TARGET_TIMEZONE.

We keep this simple and data-informed: weekday evenings + weekend mornings tend
to perform best for wholesome/relaxing content. Tune freely.
"""
from __future__ import annotations

import datetime as dt

import pytz

from config import settings

# Preferred local-time slots per platform (24h). First upload = long vlog,
# the rest are staggered teaser Shorts through the day.
PEAK_SLOTS = {
    "youtube_long": (15, 0),   # 3:00 PM — long vlog (afternoon discovery)
    "shorts": [(7, 30), (12, 0), (18, 0), (20, 30)],  # staggered teasers
    "instagram": [(11, 0), (19, 0)],
    "facebook": [(9, 0), (13, 0)],
}


def tz():
    return pytz.timezone(settings.target_timezone)


def next_slot(hour: int, minute: int, base: dt.datetime | None = None) -> dt.datetime:
    """Next occurrence of a local HH:MM in the target timezone (today or tomorrow)."""
    zone = tz()
    now = base.astimezone(zone) if base else dt.datetime.now(zone)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += dt.timedelta(days=1)
    return candidate


def rfc3339(when: dt.datetime) -> str:
    """YouTube API wants UTC RFC3339 (e.g. 2026-07-24T19:00:00Z)."""
    return when.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def long_vlog_publish_time() -> dt.datetime:
    return next_slot(*PEAK_SLOTS["youtube_long"])


def shorts_publish_times(count: int) -> list[dt.datetime]:
    slots = PEAK_SLOTS["shorts"]
    return [next_slot(*slots[i % len(slots)]) for i in range(count)]


if __name__ == "__main__":
    print("Timezone:", settings.target_timezone)
    print("Long vlog publish:", long_vlog_publish_time())
    for i, t in enumerate(shorts_publish_times(4), 1):
        print(f"Short {i} publish:", t, "->", rfc3339(t))
