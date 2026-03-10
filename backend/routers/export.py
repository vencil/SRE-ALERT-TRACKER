"""Export router — CSV/JSON/Markdown download endpoints for reports and alerts."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, subqueryload

from database import get_db
from models.alert_record import AlertRecord
from models.shift_report import ShiftReport
from services.alert_query import apply_alert_filters
from services.export_service import (
    export_alerts_csv,
    export_report_csv,
    export_report_json,
    export_report_markdown,
)

router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("/report/{report_id}")
def export_report(
    report_id: int,
    format: str = Query("csv", pattern="^(csv|json|md)$"),
    db: Session = Depends(get_db),
):
    """Export a single report's alerts as CSV, JSON, or Markdown."""
    report = db.query(ShiftReport).filter(ShiftReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    filename = f"report_{report.year}_W{report.week_number:02d}"

    if format == "json":
        content = export_report_json(db, report_id)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
    elif format == "md":
        content = export_report_markdown(db, report_id)
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
        )
    else:
        content = export_report_csv(db, report_id)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )


@router.get("/alerts")
def export_alerts(
    cluster_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    label_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    week: Optional[int] = Query(None),
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """Export filtered alerts as CSV."""
    query = db.query(AlertRecord).options(subqueryload(AlertRecord.labels))
    query = apply_alert_filters(
        query,
        cluster_id=cluster_id, severity=severity,
        label_id=label_id, year=year, week=week,
    )

    alerts = (
        query.order_by(AlertRecord.last_firing_at.desc().nullslast())
        .limit(limit)
        .all()
    )

    content = export_alerts_csv(db, alerts)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="alerts_export.csv"'},
    )
