"""Report generator — auto-create weekly shift reports and daily sections."""

import logging
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.daily_section import DailySection
from models.shift_report import ShiftReport
from services.timezone_utils import today_in_display_tz

logger = logging.getLogger("alert-tracker.report-gen")


def ensure_report_and_section(db: Session, target_date: date) -> DailySection:
    """Ensure a shift report and daily section exist for the given date.

    Creates them if they don't exist. Returns the DailySection.
    Uses ISO week numbering (week starts on Monday).
    Handles concurrent creation via IntegrityError catch + re-query.
    """
    iso_cal = target_date.isocalendar()
    year = iso_cal[0]
    week = iso_cal[1]

    # Find or create report (with race condition guard)
    report = (
        db.query(ShiftReport)
        .filter(ShiftReport.year == year, ShiftReport.week_number == week)
        .first()
    )
    if not report:
        try:
            report = create_weekly_report(db, year, week)
            db.flush()
            logger.info("Auto-created report for %d-W%02d", year, week)
        except IntegrityError:
            db.rollback()
            report = (
                db.query(ShiftReport)
                .filter(ShiftReport.year == year, ShiftReport.week_number == week)
                .first()
            )
            logger.info("Report for %d-W%02d created by concurrent process", year, week)

    # Find or create daily section (with race condition guard)
    section = (
        db.query(DailySection)
        .filter(
            DailySection.report_id == report.id,
            DailySection.section_date == target_date,
        )
        .first()
    )
    if not section:
        try:
            section = DailySection(
                report_id=report.id,
                section_date=target_date,
            )
            db.add(section)
            db.flush()
            logger.info("Auto-created daily section for %s", target_date)
        except IntegrityError:
            db.rollback()
            section = (
                db.query(DailySection)
                .filter(
                    DailySection.report_id == report.id,
                    DailySection.section_date == target_date,
                )
                .first()
            )
            logger.info("Section for %s created by concurrent process", target_date)

    return section


def create_weekly_report(db: Session, year: int, week: int) -> ShiftReport:
    """Create a blank weekly report with 7 daily sections (Mon-Sun)."""
    report = ShiftReport(year=year, week_number=week)
    db.add(report)
    db.flush()

    # Create 7 daily sections
    week_start = date.fromisocalendar(year, week, 1)  # Monday
    for i in range(7):
        section = DailySection(
            report_id=report.id,
            section_date=week_start + timedelta(days=i),
        )
        db.add(section)

    db.flush()
    return report


def generate_current_week_report(db: Session) -> ShiftReport:
    """Generate (or return existing) report for the current week.

    Called by APScheduler every Monday 00:00.
    """
    today = today_in_display_tz()
    iso_cal = today.isocalendar()
    year = iso_cal[0]
    week = iso_cal[1]

    existing = (
        db.query(ShiftReport)
        .filter(ShiftReport.year == year, ShiftReport.week_number == week)
        .first()
    )
    if existing:
        logger.info("Report for %d-W%02d already exists", year, week)
        return existing

    try:
        report = create_weekly_report(db, year, week)
        db.commit()
        logger.info("Generated new weekly report for %d-W%02d", year, week)
        return report
    except IntegrityError:
        # Concurrent process created the report — fetch and return
        db.rollback()
        existing = (
            db.query(ShiftReport)
            .filter(ShiftReport.year == year, ShiftReport.week_number == week)
            .first()
        )
        logger.info("Report for %d-W%02d created by concurrent process", year, week)
        return existing
