"""Dedup logic — fingerprint-based alert deduplication within a report week."""

import hashlib
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.alert_record import AlertRecord
from models.daily_section import DailySection

logger = logging.getLogger("alert-tracker.dedup")


def compute_fingerprint(labels: dict[str, str]) -> str:
    """Compute a SHA-256 fingerprint from a sorted label set.

    Used when Alertmanager doesn't provide a fingerprint (e.g., Prometheus query_range).
    """
    sorted_pairs = sorted(labels.items())
    raw = "|".join(f"{k}={v}" for k, v in sorted_pairs)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def upsert_alert(
    db: Session,
    daily_section: DailySection,
    cluster_id: int,
    fingerprint: str,
    alert_name: str,
    severity: str,
    instance: Optional[str],
    source_group: Optional[str],
    runbook_url: Optional[str],
    firing_at: Optional[datetime],
    auto_resolved: bool = False,
) -> AlertRecord:
    """Insert or update an alert record based on fingerprint within the same report week.

    Dedup logic:
    - Same (fingerprint, report_id) → UPDATE occurrence_count, last_firing_at
    - Different → INSERT new record
    """
    report_id = daily_section.report_id

    # Find existing alert with same fingerprint in the same report week.
    # Use with_for_update() to prevent race conditions in concurrent pollers
    # (no-op on SQLite which uses file-level locking, effective on MariaDB).
    existing = (
        db.query(AlertRecord)
        .join(DailySection)
        .filter(
            DailySection.report_id == report_id,
            AlertRecord.fingerprint == fingerprint,
        )
        .with_for_update()
        .first()
    )

    if existing:
        # Update existing record
        existing.occurrence_count += 1
        if firing_at and (existing.last_firing_at is None or firing_at > existing.last_firing_at):
            existing.last_firing_at = firing_at
        if auto_resolved:
            existing.auto_resolved = True
        logger.debug(
            "Dedup: updated alert %s (fp=%s), count=%d",
            alert_name, fingerprint[:8], existing.occurrence_count,
        )
        return existing
    else:
        # Insert new record
        new_alert = AlertRecord(
            daily_section_id=daily_section.id,
            cluster_id=cluster_id,
            fingerprint=fingerprint,
            alert_name=alert_name,
            severity=severity,
            instance=instance,
            source_group=source_group,
            runbook_url=runbook_url,
            occurrence_count=1,
            first_firing_at=firing_at,
            last_firing_at=firing_at,
            auto_resolved=auto_resolved,
        )
        db.add(new_alert)
        logger.debug(
            "Dedup: inserted new alert %s (fp=%s)",
            alert_name, fingerprint[:8],
        )
        return new_alert
