"""Export service — generate CSV/JSON from report and alert data."""

import csv
import io
import json
from typing import Any

from sqlalchemy.orm import Session, joinedload, subqueryload

from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.shift_report import ShiftReport


def _alert_to_dict(alert: AlertRecord) -> dict[str, Any]:
    """Convert alert record to flat dictionary for export."""
    return {
        "id": alert.id,
        "alert_name": alert.alert_name,
        "severity": alert.severity,
        "instance": alert.instance or "",
        "cluster_name": alert.cluster.name if alert.cluster else "",
        "fingerprint": alert.fingerprint or "",
        "occurrence_count": alert.occurrence_count,
        "phenomenon": alert.phenomenon or "",
        "impact": alert.impact or "",
        "action_taken": alert.action_taken or "",
        "labels": ", ".join(l.name for l in alert.labels) if alert.labels else "",
        "first_firing_at": str(alert.first_firing_at) if alert.first_firing_at else "",
        "last_firing_at": str(alert.last_firing_at) if alert.last_firing_at else "",
        "section_date": str(alert.daily_section.section_date) if alert.daily_section else "",
    }


def export_report_csv(db: Session, report_id: int) -> str:
    """Export a single report's alerts as CSV string."""
    report = (
        db.query(ShiftReport)
        .options(
            joinedload(ShiftReport.daily_sections)
            .joinedload(DailySection.alert_records)
            .subqueryload(AlertRecord.labels),
            joinedload(ShiftReport.daily_sections)
            .joinedload(DailySection.alert_records)
            .joinedload(AlertRecord.cluster),
        )
        .filter(ShiftReport.id == report_id)
        .first()
    )
    if not report:
        return ""

    alerts = []
    for section in report.daily_sections:
        for alert in section.alert_records:
            alerts.append(_alert_to_dict(alert))

    return _dicts_to_csv(alerts)


def export_report_json(db: Session, report_id: int) -> str:
    """Export a single report's alerts as JSON string."""
    report = (
        db.query(ShiftReport)
        .options(
            joinedload(ShiftReport.daily_sections)
            .joinedload(DailySection.alert_records)
            .subqueryload(AlertRecord.labels),
            joinedload(ShiftReport.daily_sections)
            .joinedload(DailySection.alert_records)
            .joinedload(AlertRecord.cluster),
        )
        .filter(ShiftReport.id == report_id)
        .first()
    )
    if not report:
        return "[]"

    alerts = []
    for section in report.daily_sections:
        for alert in section.alert_records:
            alerts.append(_alert_to_dict(alert))

    return json.dumps(alerts, ensure_ascii=False, indent=2)


def export_alerts_csv(db: Session, alerts: list[AlertRecord]) -> str:
    """Export a list of alerts as CSV string."""
    return _dicts_to_csv([_alert_to_dict(a) for a in alerts])


def _dicts_to_csv(rows: list[dict]) -> str:
    """Convert list of dicts to CSV string."""
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
