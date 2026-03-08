"""Alerts router — query, update, and label management for alert records."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload, subqueryload

from database import get_db
from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.label import Label
from models.shift_report import ShiftReport
from schemas.alert import AlertLabelAction, AlertListResponse, AlertOut, AlertUpdate

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

    if cluster_id is not None:
        query = query.filter(AlertRecord.cluster_id == cluster_id)
    if severity is not None:
        query = query.filter(AlertRecord.severity == severity)
    if label_id is not None:
        query = query.filter(AlertRecord.labels.any(Label.id == label_id))
    if year is not None or week is not None:
        query = query.join(DailySection).join(ShiftReport)
        if year is not None:
            query = query.filter(ShiftReport.year == year)
        if week is not None:
            query = query.filter(ShiftReport.week_number == week)

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
