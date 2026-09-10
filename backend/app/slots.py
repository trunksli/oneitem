"""
Publishing slots: a new pick four times a day, anchored to a timezone.

ONE used to publish hourly. It now publishes at fixed local times -- by default
6am, 12pm, 6pm and midnight US Eastern -- which suits a reader who wants fewer,
better things rather than a feed.

The slots are anchored to a timezone rather than to UTC on purpose. UTC slots at
00/06/12/18 land at 2am Eastern, which wastes a quarter of the output on the
core audience. Anchoring also makes daylight saving invisible to readers: the
morning pick is always at 6am local, and only the UTC offset moves.

Everything is returned as naive UTC datetimes, matching how publish_time is
stored, so callers never handle timezones themselves.

Configure with SLOT_TIMEZONE (an IANA name) and SLOT_HOURS (local hours, comma
separated). Avoid 2am local: it does not exist, or exists twice, on DST changes.
"""
import datetime
import os

SLOT_TIMEZONE = os.getenv("SLOT_TIMEZONE", "America/New_York")
SLOT_HOURS = sorted({int(h) for h in os.getenv("SLOT_HOURS", "0,6,12,18").split(",") if h.strip()})
SLOTS_PER_DAY = len(SLOT_HOURS)

_tz_cache = []


def _tz():
    """The slot timezone: zoneinfo on modern Python, pytz on older ones."""
    if not _tz_cache:
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+
            _tz_cache.append(ZoneInfo(SLOT_TIMEZONE))
        except Exception:
            import pytz
            _tz_cache.append(pytz.timezone(SLOT_TIMEZONE))
    return _tz_cache[0]


def _localize(naive_local, tz):
    # pytz zones must be attached with localize(); replace() gives a wrong offset
    if hasattr(tz, "localize"):
        return tz.localize(naive_local)
    return naive_local.replace(tzinfo=tz)


def _utc_naive(aware):
    return aware.astimezone(datetime.timezone.utc).replace(tzinfo=None)


def slot_start(at=None):
    """Start of the slot containing `at` (naive UTC; default now), as naive UTC."""
    tz = _tz()
    moment = at or datetime.datetime.utcnow()
    local = moment.replace(tzinfo=datetime.timezone.utc).astimezone(tz)

    day = local.date()
    earlier = [h for h in SLOT_HOURS if h <= local.hour]
    if earlier:
        hour = earlier[-1]
    else:
        # Before today's first slot: still inside yesterday's last one
        hour = SLOT_HOURS[-1]
        day = day - datetime.timedelta(days=1)

    return _utc_naive(_localize(datetime.datetime(day.year, day.month, day.day, hour), tz))


def next_slot_start(at=None):
    """Start of the slot after the one containing `at`, as naive UTC."""
    current = slot_start(at)
    probe = current
    for _ in range(72):  # hour steps; far more than any gap between slots
        probe += datetime.timedelta(hours=1)
        candidate = slot_start(probe)
        if candidate > current:
            return candidate
    return current + datetime.timedelta(hours=24 // max(1, SLOTS_PER_DAY))


def upcoming_slots(count, at=None):
    """The current slot and the ones after it, `count` in total."""
    slots = [slot_start(at)]
    while len(slots) < count:
        slots.append(next_slot_start(slots[-1]))
    return slots


def seconds_until_next_slot(at=None):
    moment = at or datetime.datetime.utcnow()
    return max(60, (next_slot_start(moment) - moment).total_seconds() + 5)
