"""Dashboard router — trend analytics and top alert aggregation."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.orm import Session

from database import get_db
from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.shift_report import ShiftReport

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/trends")
def get_trends(
    weeks: int = Query(12, ge=1, le=52, description="Number of recent weeks"),
    cluster_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get weekly alert count trends, optionally per-cluster."""
    query = (
        db.query(
            ShiftReport.year,
            ShiftReport.week_number,
            AlertRecord.cluster_id,
            sa_func.count(AlertRecord.id).label("alert_count"),
        )
        .join(DailySection, DailySection.report_id == ShiftReport.id)
        .join(AlertRecord, AlertRecord.daily_section_id == DailySection.id)
    )
    if cluster_id is not None:
        query = query.filter(AlertRecord.cluster_id == cluster_id)

    rows = (
        query.group_by(ShiftReport.year, ShiftReport.week_number, AlertRecord.cluster_id)
        .order_by(ShiftReport.year.desc(), ShiftReport.week_number.desc())
        .limit(weeks * 20)  # generous limit for multi-cluster
        .all()
    )

    trends = [
        {
            "year": r.year,
            "week_number": r.week_number,
            "cluster_id": r.cluster_id,
            "alert_count": r.alert_count,
        }
        for r in rows
    ]
    return {"trends": trends}


@router.get("/top-alerts")
def get_top_alerts(
    n: int = Query(10, ge=1, le=50, description="Top N alerts"),
    weeks: int = Query(4, ge=1, le=52, description="Look-back weeks"),
    severity: Optional[str] = Query(None),
    cluster_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get top-N most frequent alert names across recent weeks."""
    query = (
        db.query(
            AlertRecord.alert_name,
            AlertRecord.severity,
            sa_func.sum(AlertRecord.occurrence_count).label("total_count"),
            sa_func.count(AlertRecord.id).label("record_count"),
        )
        .join(DailySection, DailySection.id == AlertRecord.daily_section_id)
        .join(ShiftReport, ShiftReport.id == DailySection.report_id)
    )
    if severity:
        query = query.filter(AlertRecord.severity == severity)
    if cluster_id is not None:
        query = query.filter(AlertRecord.cluster_id == cluster_id)

    # Only look at the last N weeks — use recent reports
    recent_ids = (
        select(ShiftReport.id)
        .order_by(ShiftReport.year.desc(), ShiftReport.week_number.desc())
        .limit(weeks)
    )
    query = query.filter(ShiftReport.id.in_(recent_ids))

    rows = (
        query.group_by(AlertRecord.alert_name, AlertRecord.severity)
        .order_by(sa_func.sum(AlertRecord.occurrence_count).desc())
        .limit(n)
        .all()
    )

    top_alerts = [
        {
            "alert_name": r.alert_name,
            "severity": r.severity,
            "total_count": r.total_count,
            "record_count": r.record_count,
        }
        for r in rows
    ]
    return {"top_alerts": top_alerts}


@router.get("/severity-distribution")
def get_severity_distribution(
    weeks: int = Query(4, ge=1, le=52),
    db: Session = Depends(get_db),
):
    """Get alert count breakdown by severity."""
    recent_ids = (
        select(ShiftReport.id)
        .order_by(ShiftReport.year.desc(), ShiftReport.week_number.desc())
        .limit(weeks)
    )

    rows = (
        db.query(
            AlertRecord.severity,
            sa_func.count(AlertRecord.id).label("count"),
        )
        .join(DailySection, DailySection.id == AlertRecord.daily_section_id)
        .join(ShiftReport, ShiftReport.id == DailySection.report_id)
        .filter(ShiftReport.id.in_(recent_ids))
        .filter(AlertRecord.severity.isnot(None))
        .group_by(AlertRecord.severity)
        .all()
    )

    return {"distribution": [{"severity": r.severity, "count": r.count} for r in rows]}
