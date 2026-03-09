"""Export service — generate CSV/JSON/Markdown from report and alert data."""

import csv
import io
import json
from typing import Any

from sqlalchemy.orm import Session, joinedload, subqueryload

from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.shift_report import ShiftReport
from services.timezone_utils import to_display_tz

_SEVERITY_ICONS = {"critical": "\U0001f534", "warning": "\U0001f7e1", "info": "\U0001f535"}


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


def _load_report(db: Session, report_id: int) -> ShiftReport | None:
    """Load a ShiftReport with all nested data eagerly loaded."""
    return (
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


def export_report_csv(db: Session, report_id: int) -> str:
    """Export a single report's alerts as CSV string."""
    report = _load_report(db, report_id)
    if not report:
        return ""

    alerts = []
    for section in report.daily_sections:
        for alert in section.alert_records:
            alerts.append(_alert_to_dict(alert))

    return _dicts_to_csv(alerts)


def export_report_json(db: Session, report_id: int) -> str:
    """Export a single report's alerts as JSON string."""
    report = _load_report(db, report_id)
    if not report:
        return "[]"

    alerts = []
    for section in report.daily_sections:
        for alert in section.alert_records:
            alerts.append(_alert_to_dict(alert))

    return json.dumps(alerts, ensure_ascii=False, indent=2)


def export_report_markdown(db: Session, report_id: int) -> str:
    """Export a single report as a structured Markdown document.

    Format:
      # Week report heading + operator
      ## Daily sections (Mon-Sun)
        ### Alert cards with severity icon, metadata, and manual fields
    """
    report = _load_report(db, report_id)
    if not report:
        return ""

    lines: list[str] = []
    operator = report.operator_name or "(未指定)"
    lines.append(f"# 週報 {report.year}-W{report.week_number:02d}")
    lines.append("")
    lines.append(f"**值班人員：** {operator}")
    if report.notes:
        lines.append(f"**備註：** {report.notes}")
    lines.append("")

    # Sort daily sections by date
    sections = sorted(report.daily_sections, key=lambda s: s.section_date)

    total_alerts = 0
    total_filled = 0

    for section in sections:
        weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        wd = section.section_date.weekday()
        day_label = weekday_names[wd] if wd < 7 else ""
        section_op = section.operator_name or operator

        alerts = sorted(section.alert_records, key=lambda a: (
            {"critical": 0, "warning": 1}.get(a.severity, 2),
            -(a.occurrence_count or 0),
        ))

        lines.append(f"## {section.section_date} ({day_label}) — {section_op}  [{len(alerts)} alerts]")
        lines.append("")

        if section.daily_notes:
            lines.append(f"> {section.daily_notes}")
            lines.append("")

        if not alerts:
            lines.append("*No alerts.*")
            lines.append("")
            continue

        for alert in alerts:
            total_alerts += 1
            icon = _SEVERITY_ICONS.get(alert.severity, "\u26aa")
            cluster = alert.cluster.name if alert.cluster else "?"
            lines.append(f"### {icon} {alert.alert_name}")
            lines.append("")

            # Metadata line
            meta_parts = [
                f"Severity: **{alert.severity}**",
                f"Cluster: {cluster}",
            ]
            if alert.instance:
                meta_parts.append(f"Instance: `{alert.instance}`")
            meta_parts.append(f"Count: {alert.occurrence_count}")
            if alert.first_firing_at:
                first_disp = to_display_tz(alert.first_firing_at)
                meta_parts.append(f"First: {first_disp:%Y-%m-%d %H:%M}")
            if alert.last_firing_at:
                last_disp = to_display_tz(alert.last_firing_at)
                meta_parts.append(f"Last: {last_disp:%Y-%m-%d %H:%M}")
            lines.append(" | ".join(meta_parts))
            lines.append("")

            if alert.labels:
                tag_str = " ".join(f"`{l.name}`" for l in alert.labels)
                lines.append(f"Labels: {tag_str}")
                lines.append("")

            if alert.runbook_url:
                lines.append(f"Runbook: {alert.runbook_url}")
                lines.append("")

            # Manual fields
            has_manual = any([alert.phenomenon, alert.impact, alert.action_taken])
            if has_manual:
                total_filled += 1
                if alert.phenomenon:
                    lines.append(f"**現象：** {alert.phenomenon}")
                    lines.append("")
                if alert.impact:
                    lines.append(f"**影響：** {alert.impact}")
                    lines.append("")
                if alert.action_taken:
                    lines.append(f"**處理作法：** {alert.action_taken}")
                    lines.append("")
            else:
                lines.append("*（尚未填寫處理紀錄）*")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Summary footer
    lines.append(f"**統計：** {total_alerts} alerts, {total_filled} 已填寫處理紀錄")
    lines.append("")

    return "\n".join(lines)


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
