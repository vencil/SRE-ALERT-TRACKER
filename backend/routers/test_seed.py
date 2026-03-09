"""Test seed router — Lab-only endpoint for E2E test data setup.

Only available when AT_AUTH_MODE=none (Lab environment).
Production deployments (oauth2-proxy) will never register this router.
"""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.cluster import Cluster
from services.dedup import compute_fingerprint, upsert_alert
from services.report_generator import ensure_report_and_section

logger = logging.getLogger("alert-tracker.test-seed")

router = APIRouter(prefix="/api/test", tags=["Test"])


class SeedAlert(BaseModel):
    alert_name: str
    severity: str = "warning"
    instance: str | None = None
    source_group: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class SeedRequest(BaseModel):
    cluster_name: str = "lab-cluster"
    year: int | None = None
    week_number: int | None = None
    target_date: str | None = None  # ISO format: "2026-03-09"
    alerts: list[SeedAlert] = Field(default_factory=list)


class SeedResponse(BaseModel):
    report_id: int
    year: int
    week_number: int
    section_date: str
    alert_ids: list[int]
    alert_count: int


@router.post("/seed", response_model=SeedResponse)
def seed_test_data(data: SeedRequest, db: Session = Depends(get_db)):
    """Seed test data for E2E tests. Lab-only (AT_AUTH_MODE=none)."""
    if settings.auth_mode != "none":
        raise HTTPException(status_code=404, detail="Not Found")

    # Resolve target date
    if data.target_date:
        target = date.fromisoformat(data.target_date)
    elif data.year and data.week_number:
        # Use Monday of the specified week
        target = date.fromisocalendar(data.year, data.week_number, 1)
    else:
        target = date.today()

    # Ensure cluster exists
    cluster = db.query(Cluster).filter(Cluster.name == data.cluster_name).first()
    if not cluster:
        cluster = Cluster(
            name=data.cluster_name,
            prometheus_url="http://localhost:9090",
            alertmanager_url="http://localhost:9093",
            status="healthy",
        )
        db.add(cluster)
        db.flush()

    # Ensure report + daily section
    section = ensure_report_and_section(db, target)

    # Create alerts
    alert_ids = []
    for i, alert_data in enumerate(data.alerts):
        labels = {"alertname": alert_data.alert_name, **alert_data.labels}
        if "severity" not in labels:
            labels["severity"] = alert_data.severity
        # Add index to ensure unique fingerprints
        labels["__seed_index"] = str(i)

        fingerprint = compute_fingerprint(labels)
        record = upsert_alert(
            db=db,
            daily_section=section,
            cluster_id=cluster.id,
            fingerprint=fingerprint,
            alert_name=alert_data.alert_name,
            severity=alert_data.severity,
            instance=alert_data.instance,
            source_group=alert_data.source_group,
            runbook_url=None,
            firing_at=None,
        )
        db.flush()
        alert_ids.append(record.id)

    db.commit()

    iso_cal = target.isocalendar()
    logger.info(
        "Seeded %d alerts for %d-W%02d (%s)",
        len(alert_ids), iso_cal[0], iso_cal[1], target,
    )

    return SeedResponse(
        report_id=section.report_id,
        year=iso_cal[0],
        week_number=iso_cal[1],
        section_date=target.isoformat(),
        alert_ids=alert_ids,
        alert_count=len(alert_ids),
    )
