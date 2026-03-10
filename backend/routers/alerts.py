"""Alerts router — query, update, label management, history, and AI suggestion."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload, subqueryload

from config import settings
from database import get_db
from models.alert_record import AlertRecord
from models.cluster import Cluster
from models.daily_section import DailySection
from models.label import Label
from models.shift_report import ShiftReport
from schemas.alert import AlertLabelAction, AlertListResponse, AlertOut, AlertUpdate
from services.alert_query import apply_alert_filters

logger = logging.getLogger("alert-tracker.alerts")

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


@router.get("", response_model=AlertListResponse)
def list_alerts(
    cluster_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    label_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    week: Optional[int] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List alert records with filters and pagination."""
    # Use subqueryload to avoid cartesian product from joinedload + pagination
    query = db.query(AlertRecord).options(
        subqueryload(AlertRecord.labels),
        joinedload(AlertRecord.cluster),
    )
    query = apply_alert_filters(
        query,
        cluster_id=cluster_id, severity=severity,
        label_id=label_id, year=year, week=week,
    )

    total = query.count()
    alerts = (
        query.order_by(AlertRecord.last_firing_at.desc().nullslast(), AlertRecord.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return AlertListResponse(total=total, offset=offset, limit=limit, alerts=alerts)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    """Get single alert record detail."""
    alert = (
        db.query(AlertRecord)
        .options(joinedload(AlertRecord.labels))
        .filter(AlertRecord.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: int, data: AlertUpdate, db: Session = Depends(get_db)):
    """Update alert record (manual fields + escape-hatch overrides)."""
    alert = (
        db.query(AlertRecord)
        .options(joinedload(AlertRecord.labels))
        .filter(AlertRecord.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    update_data = data.model_dump(exclude_unset=True)
    # If auto-fields are being overridden, set manually_edited flag
    auto_fields = {"alert_name", "severity", "instance"}
    if any(k in update_data for k in auto_fields):
        alert.manually_edited = True

    for key, value in update_data.items():
        setattr(alert, key, value)

    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/labels", response_model=AlertOut)
def add_label_to_alert(alert_id: int, data: AlertLabelAction, db: Session = Depends(get_db)):
    """Add a label to an alert record. Returns 200 (idempotent)."""
    alert = (
        db.query(AlertRecord)
        .options(joinedload(AlertRecord.labels))
        .filter(AlertRecord.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    label = db.query(Label).filter(Label.id == data.label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    if label not in alert.labels:
        alert.labels.append(label)
        db.commit()
        db.refresh(alert)

    return alert


@router.delete("/{alert_id}/labels/{label_id}", response_model=AlertOut)
def remove_label_from_alert(alert_id: int, label_id: int, db: Session = Depends(get_db)):
    """Remove a label from an alert record."""
    alert = (
        db.query(AlertRecord)
        .options(joinedload(AlertRecord.labels))
        .filter(AlertRecord.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    label = db.query(Label).filter(Label.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    if label in alert.labels:
        alert.labels.remove(label)
        db.commit()
        db.refresh(alert)

    return alert


@router.get("/{alert_id}/history")
def get_alert_history(
    alert_id: int,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get historical records for the same alert across different weeks.

    Strategy: fingerprint-first (exact same alert), then alert_name fallback
    (similar alerts). Only returns records that have action_taken filled.
    Excludes the current alert itself.
    """
    alert = db.query(AlertRecord).filter(AlertRecord.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Base query: join to get year/week/operator + cluster name, filter has action_taken
    base_query = (
        db.query(
            AlertRecord.id,
            AlertRecord.alert_name,
            AlertRecord.fingerprint,
            AlertRecord.severity,
            AlertRecord.occurrence_count,
            AlertRecord.phenomenon,
            AlertRecord.impact,
            AlertRecord.action_taken,
            AlertRecord.first_firing_at,
            AlertRecord.last_firing_at,
            AlertRecord.instance,
            DailySection.section_date,
            ShiftReport.year,
            ShiftReport.week_number,
            ShiftReport.operator_name,
            Cluster.name.label("cluster_name"),
        )
        .join(DailySection, DailySection.id == AlertRecord.daily_section_id)
        .join(ShiftReport, ShiftReport.id == DailySection.report_id)
        .join(Cluster, Cluster.id == AlertRecord.cluster_id)
        .filter(
            AlertRecord.id != alert_id,
            AlertRecord.action_taken.isnot(None),
            AlertRecord.action_taken != "",
        )
        .order_by(AlertRecord.last_firing_at.desc().nullslast(), AlertRecord.id.desc())
    )

    # Layer 1: exact fingerprint match (same alert identity across weeks)
    fp_rows = (
        base_query
        .filter(AlertRecord.fingerprint == alert.fingerprint)
        .limit(limit)
        .all()
    )

    # Layer 2: alert_name fallback (similar alerts, different instances)
    remaining = limit - len(fp_rows)
    name_rows = []
    if remaining > 0:
        fp_ids = {r.id for r in fp_rows}
        name_query = (
            base_query
            .filter(
                AlertRecord.alert_name == alert.alert_name,
                AlertRecord.fingerprint != alert.fingerprint,
            )
            .limit(remaining)
        )
        name_rows = [r for r in name_query.all() if r.id not in fp_ids]

    def _row_to_dict(row, match_type: str) -> dict:
        return {
            "id": row.id,
            "alert_name": row.alert_name,
            "fingerprint": row.fingerprint,
            "severity": row.severity,
            "occurrence_count": row.occurrence_count,
            "phenomenon": row.phenomenon,
            "impact": row.impact,
            "action_taken": row.action_taken,
            "first_firing_at": row.first_firing_at.isoformat() if row.first_firing_at else None,
            "last_firing_at": row.last_firing_at.isoformat() if row.last_firing_at else None,
            "instance": row.instance,
            "section_date": row.section_date.isoformat() if row.section_date else None,
            "year": row.year,
            "week_number": row.week_number,
            "operator_name": row.operator_name,
            "cluster_name": row.cluster_name,
            "match_type": match_type,
        }

    records = (
        [_row_to_dict(r, "fingerprint") for r in fp_rows]
        + [_row_to_dict(r, "alert_name") for r in name_rows]
    )

    return {
        "alert_id": alert_id,
        "alert_name": alert.alert_name,
        "fingerprint": alert.fingerprint,
        "total": len(records),
        "records": records,
    }


@router.post("/{alert_id}/suggest")
async def suggest_action(alert_id: int, db: Session = Depends(get_db)):
    """Generate an AI-powered handling suggestion based on historical records.

    Requires AT_LLM_PROVIDER to be configured. Returns 501 if LLM is disabled.
    Uses the same history lookup as /history (fingerprint-first, alert_name fallback).
    """
    if not settings.llm_enabled:
        raise HTTPException(status_code=501, detail="AI suggestion not enabled (AT_LLM_PROVIDER not configured)")

    alert = (
        db.query(AlertRecord)
        .options(joinedload(AlertRecord.cluster))
        .filter(AlertRecord.id == alert_id)
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Gather history (reuse the same query logic as /history)
    history_query = (
        db.query(
            AlertRecord.action_taken,
            AlertRecord.phenomenon,
            AlertRecord.impact,
            AlertRecord.severity,
            AlertRecord.occurrence_count,
            ShiftReport.year,
            ShiftReport.week_number,
            ShiftReport.operator_name,
        )
        .join(DailySection, DailySection.id == AlertRecord.daily_section_id)
        .join(ShiftReport, ShiftReport.id == DailySection.report_id)
        .filter(
            AlertRecord.id != alert_id,
            AlertRecord.action_taken.isnot(None),
            AlertRecord.action_taken != "",
        )
        .order_by(AlertRecord.last_firing_at.desc().nullslast())
    )

    # Fingerprint match first, then alert_name fallback.
    # NOTE: These queries use .join() (INNER JOIN) not .joinedload(),
    # so .limit() safely applies to the primary table rows.
    # If labels are needed here in the future, use .selectinload() (not joinedload).
    fp_rows = history_query.filter(AlertRecord.fingerprint == alert.fingerprint).limit(10).all()
    remaining = 10 - len(fp_rows)
    name_rows = []
    if remaining > 0:
        name_rows = (
            history_query
            .filter(AlertRecord.alert_name == alert.alert_name, AlertRecord.fingerprint != alert.fingerprint)
            .limit(remaining)
            .all()
        )

    history_records = [
        {
            "action_taken": r.action_taken,
            "phenomenon": r.phenomenon,
            "impact": r.impact,
            "severity": r.severity,
            "occurrence_count": r.occurrence_count,
            "year": r.year,
            "week_number": r.week_number,
            "operator_name": r.operator_name,
        }
        for r in (list(fp_rows) + list(name_rows))
    ]

    cluster_name = alert.cluster.name if alert.cluster else None

    try:
        # Lazy import: llm_service has httpx dependency and should not be
        # imported at module level when AT_LLM_PROVIDER=none (most deployments).
        from services.llm_service import generate_suggestion
        suggestion = await generate_suggestion(
            alert_name=alert.alert_name,
            severity=alert.severity,
            phenomenon=alert.phenomenon,
            cluster_name=cluster_name,
            history_records=history_records,
        )
    except Exception:
        logger.exception("LLM suggestion failed for alert %d", alert_id)
        raise HTTPException(status_code=502, detail="AI suggestion failed — check server logs for details")

    return {
        "alert_id": alert_id,
        "suggestion": suggestion,
        "history_count": len(history_records),
    }
