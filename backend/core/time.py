from datetime import UTC, datetime, timedelta

HOUR = timedelta(hours=1)


def floor_hour(t: datetime) -> datetime:
    """Floors on the UTC hour (so +05:30 offsets work) and keeps the input's timezone."""
    if t.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    floored = t.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    return floored.astimezone(t.tzinfo)


def ceil_hour(t: datetime) -> datetime:
    floored = floor_hour(t)
    return floored if floored == t else floored + HOUR
