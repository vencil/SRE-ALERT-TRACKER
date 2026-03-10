"""Dashboard router — trend analytics, top alerts, and correlation analysis."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func, select
from sqlalchemy.orm import Session

from database import get_db
from models.alert_record import AlertRecord
from models.cluster import Cluster
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


@router.get("/correlation")
def get_correlation(
    year: int = Query(..., description="Report year"),
    week: int = Query(..., ge=1, le=53, description="Report week number"),
    cluster_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Find co-occurring alerts using time-interval overlap analysis.

    Groups alerts whose [first_firing_at, last_firing_at] intervals overlap,
    revealing potential root-cause relationships (e.g., DB spike followed by
    API 500s). Only returns groups with 2+ alerts.
    """
    report = (
        db.query(ShiftReport)
        .filter(ShiftReport.year == year, ShiftReport.week_number == week)
        .first()
    )
    if not report:
        return {"year": year, "week": week, "groups": []}

    # Fetch all alerts for this week that have firing timestamps
    query = (
        db.query(
            AlertRecord.id,
            AlertRecord.alert_name,
            AlertRecord.severity,
            AlertRecord.fingerprint,
            AlertRecord.occurrence_count,
            AlertRecord.first_firing_at,
            AlertRecord.last_firing_at,
            AlertRecord.instance,
            DailySection.section_date,
            Cluster.name.label("cluster_name"),
        )
        .join(DailySection, DailySection.id == AlertRecord.daily_section_id)
        .join(Cluster, Cluster.id == AlertRecord.cluster_id)
        .filter(
            DailySection.report_id == report.id,
            AlertRecord.first_firing_at.isnot(None),
        )
    )
    if cluster_id is not None:
        query = query.filter(AlertRecord.cluster_id == cluster_id)

    rows = query.order_by(AlertRecord.first_firing_at).all()

    if not rows:
        return {"year": year, "week": week, "groups": []}

    # Interval overlap grouping using sweep-line algorithm
    # Each alert has interval [first_firing_at, last_firing_at or first_firing_at]
    intervals = []
    for r in rows:
        start = r.first_firing_at
        end = r.last_firing_at if r.last_firing_at and r.last_firing_at > start else start
        intervals.append({
            "id": r.id,
            "alert_name": r.alert_name,
            "severity": r.severity,
            "fingerprint": r.fingerprint[:8],
            "occurrence_count": r.occurrence_count,
            "first_firing_at": start.isoformat(),
            "last_firing_at": end.isoformat(),
            "instance": r.instance,
            "section_date": r.section_date.isoformat() if r.section_date else None,
            "cluster_name": r.cluster_name,
            "_start": start,
            "_end": end,
        })

    # Sort by start time, then group overlapping intervals
    intervals.sort(key=lambda x: x["_start"])
    groups = []
    current_group = [intervals[0]]
    group_end = intervals[0]["_end"]

    for item in intervals[1:]:
        if item["_start"] <= group_end:
            # Overlaps with current group
            current_group.append(item)
            if item["_end"] > group_end:
                group_end = item["_end"]
        else:
            # No overlap — finalize current group if 2+
            if len(current_group) >= 2:
                groups.append(_build_group(current_group))
            current_group = [item]
            group_end = item["_end"]

    # Don't forget the last group
    if len(current_group) >= 2:
        groups.append(_build_group(current_group))

    return {"year": year, "week": week, "groups": groups}


def _build_group(items: list[dict]) -> dict:
    """Build a correlation group summary from overlapping alert items."""
    # Remove internal fields
    clean_items = []
    for item in items:
        clean = {k: v for k, v in item.items() if not k.startswith("_")}
        clean_items.append(clean)

    starts = [i["_start"] for i in items]
    ends = [i["_end"] for i in items]

    return {
        "window_start": min(starts).isoformat(),
        "window_end": max(ends).isoformat(),
        "alert_count": len(clean_items),
        "alerts": clean_items,
    }
