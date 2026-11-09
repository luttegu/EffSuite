"""Unambiguous UTC calendar-day boundaries for publisher and customer UI."""

from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone


def utc_datetime(value: datetime) -> datetime:
    """Normalize an aware timestamp without assuming a local timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Licence dates require a timezone-aware clock")
    return value.astimezone(timezone.utc)


def expiry_after_day(day: date) -> datetime:
    """Exclusive UTC cut-off after a selected, inclusive last valid date."""
    try:
        return datetime.combine(day + timedelta(days=1), time(), tzinfo=timezone.utc)
    except OverflowError as exc:
        raise ValueError("Choose a last valid date before 31 December 9999") from exc


def whole_last_day(expires: datetime) -> date | None:
    """Return an included whole UTC day only for a midnight cut-off."""
    expires = utc_datetime(expires)
    if expires.time() != time():
        return None
    try:
        return expires.date() - timedelta(days=1)
    except OverflowError:
        return None


def readable_day(day: date) -> str:
    """Spell out the month to avoid day/month ambiguity."""
    return day.strftime("%d %B %Y")


def readable_utc(value: datetime) -> str:
    """Human-readable exact instant, always labelled UTC."""
    return utc_datetime(value).strftime("%d %B %Y at %H:%M:%S UTC")
