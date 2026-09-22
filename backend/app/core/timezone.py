from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from core.config import settings


def get_zone(zone_name: str | None = None) -> ZoneInfo:
    try:
        return ZoneInfo(zone_name or settings.DEFAULT_TIMEZONE)
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def as_company_tz(dt: datetime, zone_name: str | None = None) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_zone(zone_name))


def company_now(zone_name: str | None = None) -> datetime:
    return datetime.now(timezone.utc).astimezone(get_zone(zone_name))


def local_date(dt: datetime, zone_name: str | None = None) -> date:
    return as_company_tz(dt, zone_name).date()


def combine_naive(day: date, t: time | None) -> datetime:
    """Combine a date and a naive time into a zone-aware datetime (company tz)."""
    if t is None:
        t = time(0, 0)
    localized = datetime.combine(day, t)
    return localized.replace(tzinfo=get_zone())


def shift_work_datetime(start_time: datetime, end_time: datetime) -> tuple[datetime, datetime]:
    """Return concrete shift start/end for log pairing given the start timestamp of the shift day."""
    return start_time, end_time


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def add_days(d: date, days: int) -> date:
    return d + timedelta(days=days)