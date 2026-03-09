"""Tests for timezone_utils — display timezone conversion and week boundaries."""

import os
from datetime import date, datetime, timezone

import pytest

os.environ.setdefault("TESTING", "1")


class TestGetDisplayTz:
    def test_returns_zoneinfo(self):
        from services.timezone_utils import get_display_tz
        tz = get_display_tz()
        assert str(tz) == "Asia/Taipei"

    def test_now_in_display_tz_is_aware(self):
        from services.timezone_utils import now_in_display_tz
        now = now_in_display_tz()
        assert now.tzinfo is not None

    def test_today_in_display_tz_returns_date(self):
        from services.timezone_utils import today_in_display_tz
        today = today_in_display_tz()
        assert isinstance(today, date)


class TestToDisplayTz:
    def test_none_returns_none(self):
        from services.timezone_utils import to_display_tz
        assert to_display_tz(None) is None

    def test_utc_to_taipei(self):
        """UTC 16:00 = Asia/Taipei 00:00 next day."""
        from services.timezone_utils import to_display_tz
        utc_naive = datetime(2026, 3, 9, 16, 0, 0)  # Monday 16:00 UTC
        result = to_display_tz(utc_naive)
        assert result.date() == date(2026, 3, 10)  # Tuesday in Taipei
        assert result.hour == 0

    def test_utc_midnight_to_taipei(self):
        """UTC 00:00 = Asia/Taipei 08:00 same day."""
        from services.timezone_utils import to_display_tz
        utc_naive = datetime(2026, 3, 9, 0, 0, 0)
        result = to_display_tz(utc_naive)
        assert result.date() == date(2026, 3, 9)
        assert result.hour == 8


class TestUtcNow:
    def test_utc_now_is_naive(self):
        from services.timezone_utils import utc_now
        now = utc_now()
        assert now.tzinfo is None


class TestIsoMondayOf:
    def test_monday_returns_itself(self):
        from services.timezone_utils import iso_monday_of
        monday = date(2026, 3, 9)  # Monday
        assert iso_monday_of(monday) == monday

    def test_sunday_returns_previous_monday(self):
        from services.timezone_utils import iso_monday_of
        sunday = date(2026, 3, 15)  # Sunday
        assert iso_monday_of(sunday) == date(2026, 3, 9)  # Monday of same week

    def test_week_boundary_taipei(self):
        """In Taipei, Monday 00:00 local = Sunday 16:00 UTC.
        An alert at UTC 16:00 Sunday should map to Monday's week in Taipei.
        """
        from services.timezone_utils import to_display_tz, iso_monday_of
        utc_naive = datetime(2026, 3, 8, 16, 0, 0)  # Sunday 16:00 UTC
        display_date = to_display_tz(utc_naive).date()  # Monday in Taipei
        monday = iso_monday_of(display_date)
        assert monday == date(2026, 3, 9)  # Monday W11
