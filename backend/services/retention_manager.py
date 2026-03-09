"""Retention manager — purges old data based on retention policy."""

import logging
from datetime import date, datetime, timezone

from dateutil.relativedelta import relativedelta
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.shift_report import ShiftReport
from models.retention_config import RetentionConfig

logger = logging.getLogger("alert-tracker.retention")


def get_retention_config(db: Session) -> RetentionConfig:
    """Get or create the singleton retention config."""
    config = db.query(RetentionConfig).first()
    if not config:
        config = RetentionConfig(retention_months=12, purge_cron="0 3 1 * *")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def purge_old_data(db: Session, retention_months: int | None = None) -> dict:
    """Delete reports, sections, and alerts older than retention_months.

    Returns a summary of deleted counts.
    """
    config = get_retention_config(db)
    months = retention_months if retention_months is not None else config.retention_months

    cutoff_date = date.today() - relativedelta(months=months)
    logger.info("Purging data older than %s (%d months)", cutoff_date.isoformat(), months)

    # Find old reports where the latest section_date is before cutoff
    old_reports = (
        db.query(ShiftReport)
        .join(DailySection, DailySection.report_id == ShiftReport.id)
        .group_by(ShiftReport.id)
        .having(sa_func.max(DailySection.section_date) < cutoff_date)
        .all()
    )

    if not old_reports:
        logger.info("No data to purge")
        config.last_purge_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return {"reports_deleted": 0, "sections_deleted": 0, "alerts_deleted": 0}

    report_ids = [r.id for r in old_reports]

    # Count before deletion
    sections_count = (
        db.query(DailySection)
        .filter(DailySection.report_id.in_(report_ids))
        .count()
    )

    section_ids = [
        s.id for s in
        db.query(DailySection.id)
        .filter(DailySection.report_id.in_(report_ids))
        .all()
    ]

    alerts_count = (
        db.query(AlertRecord)
        .filter(AlertRecord.daily_section_id.in_(section_ids))
        .count()
    ) if section_ids else 0

    # Delete in order: alerts → sections → reports (cascade should handle, but be explicit)
    try:
        if section_ids:
            db.query(AlertRecord).filter(
                AlertRecord.daily_section_id.in_(section_ids)
            ).delete(synchronize_session="fetch")

        db.query(DailySection).filter(
            DailySection.report_id.in_(report_ids)
        ).delete(synchronize_session="fetch")

        db.query(ShiftReport).filter(
            ShiftReport.id.in_(report_ids)
        ).delete(synchronize_session="fetch")

        config.last_purge_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Purge failed during bulk delete")
        raise

    result = {
        "reports_deleted": len(report_ids),
        "sections_deleted": sections_count,
        "alerts_deleted": alerts_count,
    }
    logger.info("Purge complete: %s", result)
    return result
