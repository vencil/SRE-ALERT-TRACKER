"""Tests for report generator — auto-creation of weekly reports and daily sections."""

from datetime import date

from models.daily_section import DailySection
from models.shift_report import ShiftReport
from services.report_generator import create_weekly_report, ensure_report_and_section


class TestCreateWeeklyReport:
    def test_creates_report_with_7_sections(self, db_session):
        report = create_weekly_report(db_session, 2026, 11)
        db_session.flush()

        assert report.year == 2026
        assert report.week_number == 11

        sections = (
            db_session.query(DailySection)
            .filter(DailySection.report_id == report.id)
            .order_by(DailySection.section_date)
            .all()
        )
        assert len(sections) == 7

        # First section should be Monday
        assert sections[0].section_date == date(2026, 3, 9)
        # Last should be Sunday
        assert sections[6].section_date == date(2026, 3, 15)

    def test_sections_are_consecutive_days(self, db_session):
        report = create_weekly_report(db_session, 2026, 11)
        db_session.flush()

        sections = (
            db_session.query(DailySection)
            .filter(DailySection.report_id == report.id)
            .order_by(DailySection.section_date)
            .all()
        )
        for i in range(1, 7):
            delta = sections[i].section_date - sections[i - 1].section_date
            assert delta.days == 1


class TestEnsureReportAndSection:
    def test_creates_report_if_missing(self, db_session):
        section = ensure_report_and_section(db_session, date(2026, 3, 10))
        db_session.flush()

        assert section is not None
        assert section.section_date == date(2026, 3, 10)

        # Report should exist
        report = db_session.query(ShiftReport).filter(
            ShiftReport.year == 2026, ShiftReport.week_number == 11,
        ).first()
        assert report is not None

    def test_reuses_existing_report(self, db_session):
        # Create report first
        create_weekly_report(db_session, 2026, 11)
        db_session.flush()

        section = ensure_report_and_section(db_session, date(2026, 3, 10))
        db_session.flush()

        # Should still be only 1 report
        count = db_session.query(ShiftReport).filter(
            ShiftReport.year == 2026, ShiftReport.week_number == 11,
        ).count()
        assert count == 1
        assert section is not None

    def test_creates_section_for_missing_date(self, db_session):
        # This shouldn't normally happen, but ensure robustness
        report = ShiftReport(year=2026, week_number=11)
        db_session.add(report)
        db_session.flush()

        # No sections yet
        section = ensure_report_and_section(db_session, date(2026, 3, 12))
        db_session.flush()

        assert section.section_date == date(2026, 3, 12)
        assert section.report_id == report.id

    def test_idempotent(self, db_session):
        """Calling twice for the same date should return the same section."""
        s1 = ensure_report_and_section(db_session, date(2026, 3, 10))
        db_session.flush()
        s2 = ensure_report_and_section(db_session, date(2026, 3, 10))
        db_session.flush()

        assert s1.id == s2.id
