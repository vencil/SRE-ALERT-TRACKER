"""Tests for timezone-sensitive boundaries — week/day transitions in Asia/Taipei.

Uses freezegun to freeze time at critical boundary moments and verifies that
report_generator assigns alerts to the correct week and day.

Key insight: Asia/Taipei = UTC+8, so:
- Taipei Monday 00:00 = UTC Sunday 16:00
- Taipei Sunday 23:59 = UTC Sunday 15:59
An alert firing at UTC Sunday 16:00 should be assigned to NEXT week (Monday in Taipei).
"""

from datetime import date, datetime

from freezegun import freeze_time

from services.timezone_utils import (
    today_in_display_tz,
    to_display_tz,
    now_in_display_tz,
    iso_monday_of,
)
from services.report_generator import ensure_report_and_section


class TestWeekBoundaryFrozen:
    """Freeze time at week boundaries to verify correct week assignment."""

    @freeze_time("2026-03-08 15:59:00", tz_offset=0)  # UTC Sunday 15:59
    def test_sunday_late_utc_is_still_sunday_taipei(self):
        """UTC Sunday 15:59 = Taipei Sunday 23:59 → still Week 10."""
        today = today_in_display_tz()
        assert today == date(2026, 3, 8)  # Sunday
        iso_cal = today.isocalendar()
        assert iso_cal[1] == 10  # Week 10

    @freeze_time("2026-03-08 16:00:00", tz_offset=0)  # UTC Sunday 16:00
    def test_sunday_16utc_is_monday_taipei(self):
        """UTC Sunday 16:00 = Taipei Monday 00:00 → Week 11."""
        today = today_in_display_tz()
        assert today == date(2026, 3, 9)  # Monday in Taipei
        iso_cal = today.isocalendar()
        assert iso_cal[1] == 11  # Week 11

    @freeze_time("2026-03-08 16:00:00", tz_offset=0)
    def test_monday_midnight_taipei_correct_iso_monday(self):
        """At Taipei Monday 00:00, iso_monday_of should return that Monday."""
        today = today_in_display_tz()
        monday = iso_monday_of(today)
        assert monday == date(2026, 3, 9)

    @freeze_time("2026-03-14 15:59:00", tz_offset=0)  # Taipei Saturday 23:59
    def test_end_of_week_still_same_week(self):
        """Taipei Saturday 23:59 (end of ISO week) → still Week 11."""
        today = today_in_display_tz()
        assert today == date(2026, 3, 14)  # Saturday
        iso_cal = today.isocalendar()
        assert iso_cal[1] == 11


class TestDayBoundaryFrozen:
    """Freeze time at day boundaries to verify correct daily section assignment."""

    @freeze_time("2026-03-09 15:59:00", tz_offset=0)  # Taipei Monday 23:59
    def test_late_monday_taipei_still_monday(self):
        """Taipei Monday 23:59 = UTC Monday 15:59 → section_date = Monday."""
        today = today_in_display_tz()
        assert today == date(2026, 3, 9)

    @freeze_time("2026-03-09 16:00:00", tz_offset=0)  # Taipei Tuesday 00:00
    def test_utc_monday_16_is_tuesday_taipei(self):
        """UTC Monday 16:00 = Taipei Tuesday 00:00 → section_date = Tuesday."""
        today = today_in_display_tz()
        assert today == date(2026, 3, 10)  # Tuesday


class TestEnsureReportAtBoundary:
    """Integration: ensure_report_and_section creates correct report/section at boundaries."""

    @freeze_time("2026-03-08 16:00:00", tz_offset=0)  # Taipei Monday 00:00
    def test_create_report_at_week_boundary(self, db_session):
        """Alert at UTC Sunday 16:00 (= Taipei Monday 00:00) creates Week 11 report."""
        # Simulate: alert firing_at is "now" in UTC, converted to Taipei for section
        utc_firing = datetime(2026, 3, 8, 16, 0, 0)
        display_date = to_display_tz(utc_firing).date()

        section = ensure_report_and_section(db_session, display_date)
        db_session.commit()

        assert section.section_date == date(2026, 3, 9)  # Monday
        report = section.report
        assert report.year == 2026
        assert report.week_number == 11

    @freeze_time("2026-03-08 15:59:00", tz_offset=0)  # Taipei Sunday 23:59
    def test_create_report_before_boundary(self, db_session):
        """Alert at UTC Sunday 15:59 (= Taipei Sunday 23:59) creates Week 10 report."""
        utc_firing = datetime(2026, 3, 8, 15, 59, 0)
        display_date = to_display_tz(utc_firing).date()

        section = ensure_report_and_section(db_session, display_date)
        db_session.commit()

        assert section.section_date == date(2026, 3, 8)  # Sunday
        report = section.report
        assert report.year == 2026
        assert report.week_number == 10

    @freeze_time("2027-01-03 16:00:00", tz_offset=0)  # Taipei 2027-01-04 (Mon) → ISO 2027-W01
    def test_year_boundary_iso_week(self, db_session):
        """Alert crossing year boundary: Taipei 2027-01-04 (Mon) is ISO 2027-W01.

        2026-12-29 is still ISO 2026-W53; the first Monday of 2027 (Jan 4)
        is the start of ISO 2027-W01.
        """
        utc_firing = datetime(2027, 1, 3, 16, 0, 0)  # UTC Sat 16:00 = Taipei Sun 00:00? No...
        display_date = to_display_tz(utc_firing).date()

        section = ensure_report_and_section(db_session, display_date)
        db_session.commit()

        assert section.section_date == date(2027, 1, 4)  # Monday in Taipei
        report = section.report
        assert report.year == 2027
        assert report.week_number == 1
