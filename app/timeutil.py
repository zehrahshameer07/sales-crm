"""Time helpers. Timestamps are stored in UTC; "today" is the business day in the app's timezone."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from .config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_zone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def today() -> date:
    """Today's date for the sales team (India by default), not the server's UTC date."""
    return datetime.now(local_zone()).date()
