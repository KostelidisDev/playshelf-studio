"""The `published_at` format: ISO 8601, UTC, second precision."""

from datetime import datetime, timezone

PUBLISHED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_datetime(text):
    """Parses ISO 8601 into an aware UTC datetime, or returns None.

    A bare date means midnight UTC; a time without an offset is taken as UTC.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def format_published_at(value):
    return value.astimezone(timezone.utc).strftime(PUBLISHED_AT_FORMAT)


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_local(text, tz=None):
    """A published_at for display: '28 Dec 2025, 15:00' in local time (or `tz`).
    Unparseable text is returned unchanged."""
    value = parse_datetime(text)
    if value is None:
        return text or ""
    value = value.astimezone(tz)
    return f"{value.day} {value:%b %Y, %H:%M}"
