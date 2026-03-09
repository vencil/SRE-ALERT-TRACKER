"""Timezone utilities — convert between UTC (DB) and display timezone.

DB always stores naive UTC datetimes. This module provides helpers to:
1. Convert display-tz "now" to UTC for DB queries
2. Determine shift-report week boundaries in display timezone
3. Expose timezone info to the frontend via API
"""

from datetime import date, datetime, timezone
from typing import Optional

from zoneinfo import ZoneInfo

from config import settings


def get_display_tz() -> ZoneInfo:
    """Return the configured display timezone as a ZoneInfo object."""
    return ZoneInfo(settings.display_timezone)


def now_in_display_tz() -> datetime:
    """Return current time in display timezone (tz-aware)."""
    return datetime.now(timezone.utc).astimezone(get_display_tz())


def today_in_display_tz() -> date:
    """Return today's date in the display timezone.

    This is critical for shift-report week boundaries: a Monday 00:00 in
    Asia/Taipei is still Sunday in UTC. Without this, reports would be
    assigned to the wrong week.
    """
    return now_in_display_tz().date()


def utc_now() -> datetime:
    """Return current naive UTC datetime (for DB storage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_display_tz(utc_naive: Optional[datetime]) -> Optional[datetime]:
    """Convert a naive UTC datetime to display timezone (tz-aware).

    Used by export/API when returning timestamps to frontend.
    Returns None if input is None.
    """
    if utc_naive is None:
        return None
    utc_aware = utc_naive.replace(tzinfo=timezone.utc)
    return utc_aware.astimezone(get_display_tz())


def iso_monday_of(target_date: date) -> date:
    """Given a date, return the ISO Monday of that week.

    Used by report_generator to determine the correct week boundary.
    The target_date should already be in display timezone context.
    """
    iso_cal = target_date.isocalendar()
    return date.fromisocalendar(iso_cal[0], iso_cal[1], 1)
