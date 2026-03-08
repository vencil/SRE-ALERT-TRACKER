"""Alert Poller — dual-engine pull from Alertmanager + Prometheus per cluster."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models.filter_rule import AlertFilterRule

import httpx
from sqlalchemy.orm import Session

from config import settings
from models.cluster import Cluster
from models.daily_section import DailySection
from models.shift_report import ShiftReport
from services.dedup import compute_fingerprint, upsert_alert
from services.filter_engine import apply_filters, load_active_rules
from services.report_generator import ensure_report_and_section

logger = logging.getLogger("alert-tracker.poller")


async def pull_from_alertmanager(
    cluster: Cluster, client: httpx.AsyncClient,
) -> list[dict]:
    """Pull current firing alerts from Alertmanager API v2.

    Returns list of normalized alert dicts.
    """
    url = f"{cluster.alertmanager_url.rstrip('/')}/api/v2/alerts"
    try:
        resp = await client.get(url, params={"active": "true"}, timeout=settings.pull_timeout)
        resp.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error("Alertmanager pull failed for %s: %s", cluster.name, e)
        return []

    try:
        raw_alerts = resp.json()
    except (ValueError, TypeError) as e:
        logger.error("Alertmanager invalid JSON for %s: %s", cluster.name, e)
        return []
    normalized = []
    for alert in raw_alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        status = alert.get("status", {})

        # Alertmanager API v2 always provides fingerprint; fallback uses label-based
        # hash (same algorithm AM uses internally). This is safe for dedup.
        fp = alert.get("fingerprint") or compute_fingerprint(labels)
        if not alert.get("fingerprint"):
            logger.debug("Alert %s missing fingerprint, computed: %s", labels.get("alertname"), fp[:8])
        normalized.append({
            "fingerprint": fp,
            "alertname": labels.get("alertname", "unknown"),
            "severity": labels.get("severity", "warning"),
            "instance": labels.get("instance", ""),
            "group": labels.get("job", ""),
            "runbook_url": annotations.get("runbook_url", ""),
            "firing_at": _parse_time(alert.get("startsAt")),
            "auto_resolved": status.get("state") == "suppressed",
            "source": "alertmanager",
        })

    logger.info(
        "Alertmanager pull for %s: %d alerts", cluster.name, len(normalized),
    )
    return normalized


async def pull_from_prometheus(
    cluster: Cluster, client: httpx.AsyncClient, lookback_hours: int,
) -> list[dict]:
    """Pull historical alerts from Prometheus query_range API.

    Query: ALERTS{alertstate="firing"} over [now-lookback, now].
    Returns list of normalized alert dicts.
    """
    url = f"{cluster.prometheus_url.rstrip('/')}/api/v1/query_range"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(hours=lookback_hours)

    params = {
        "query": 'ALERTS{alertstate="firing"}',
        "start": start.isoformat() + "Z",
        "end": now.isoformat() + "Z",
        "step": "300",  # 5-minute resolution
    }

    try:
        resp = await client.get(url, params=params, timeout=settings.pull_timeout)
        resp.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logger.error("Prometheus pull failed for %s: %s", cluster.name, e)
        return []

    try:
        data = resp.json()
    except (ValueError, TypeError) as e:
        logger.error("Prometheus invalid JSON for %s: %s", cluster.name, e)
        return []
    if data.get("status") != "success":
        logger.error("Prometheus query error for %s: %s", cluster.name, data)
        return []

    results = data.get("data", {}).get("result", [])
    normalized = []
    seen_fps = set()

    for series in results:
        labels = series.get("metric", {})
        fp = compute_fingerprint(labels)

        # Deduplicate within this pull
        if fp in seen_fps:
            continue
        seen_fps.add(fp)

        # Get first and last firing timestamps from values
        values = series.get("values", [])
        first_ts = _ts_to_datetime(values[0][0]) if values else now
        last_ts = _ts_to_datetime(values[-1][0]) if values else now

        normalized.append({
            "fingerprint": fp,
            "alertname": labels.get("alertname", "unknown"),
            "severity": labels.get("severity", "warning"),
            "instance": labels.get(cluster.instance_label, ""),
            "group": labels.get("job", ""),
            "runbook_url": "",  # Prometheus doesn't carry annotations
            "firing_at": last_ts,
            "auto_resolved": False,
            "source": "prometheus",
        })

    logger.info(
        "Prometheus pull for %s: %d unique alert series", cluster.name, len(normalized),
    )
    return normalized


def merge_alerts(am_alerts: list[dict], pm_alerts: list[dict]) -> list[dict]:
    """Merge alerts from both engines, preferring Alertmanager data.

    Alertmanager data is preferred because it has richer annotations.
    Prometheus data fills gaps for flapping alerts.
    """
    by_fp = {}

    # Alertmanager first (preferred source)
    for alert in am_alerts:
        by_fp[alert["fingerprint"]] = alert

    # Prometheus supplements
    for alert in pm_alerts:
        fp = alert["fingerprint"]
        if fp not in by_fp:
            by_fp[fp] = alert

    return list(by_fp.values())


async def poll_cluster(
    cluster: Cluster,
    db: Session,
    lookback_hours: int,
    filter_rules: list["AlertFilterRule"],
    client: httpx.AsyncClient,
) -> dict[str, int | str]:
    """Full poll cycle for a single cluster: pull → merge → filter → dedup → write.

    Returns summary dict with counts.
    """
    # Step 1: Pull from both engines
    am_alerts = await pull_from_alertmanager(cluster, client)
    pm_alerts = await pull_from_prometheus(cluster, client, lookback_hours)

    # Step 2: Merge
    merged = merge_alerts(am_alerts, pm_alerts)
    logger.info(
        "Cluster %s: AM=%d, PM=%d, merged=%d",
        cluster.name, len(am_alerts), len(pm_alerts), len(merged),
    )

    # Step 3: Apply filters
    filtered = apply_filters(merged, filter_rules)
    logger.info(
        "Cluster %s: %d alerts after filtering (%d removed)",
        cluster.name, len(filtered), len(merged) - len(filtered),
    )

    # Step 4: For each alert, find the right daily section and upsert
    inserted = 0
    updated = 0
    for alert_data in filtered:
        firing_at = alert_data.get("firing_at") or datetime.now(timezone.utc).replace(tzinfo=None)
        section = ensure_report_and_section(db, firing_at.date())

        result = upsert_alert(
            db=db,
            daily_section=section,
            cluster_id=cluster.id,
            fingerprint=alert_data["fingerprint"],
            alert_name=alert_data["alertname"],
            severity=alert_data["severity"],
            instance=alert_data.get("instance"),
            source_group=alert_data.get("group"),
            runbook_url=alert_data.get("runbook_url"),
            firing_at=firing_at,
            auto_resolved=alert_data.get("auto_resolved", False),
        )

        if result.occurrence_count == 1:
            inserted += 1
        else:
            updated += 1

    db.commit()

    return {
        "cluster": cluster.name,
        "am_count": len(am_alerts),
        "pm_count": len(pm_alerts),
        "merged": len(merged),
        "filtered": len(filtered),
        "inserted": inserted,
        "updated": updated,
    }


async def poll_all_clusters(db: Session, interval_hours: int, lookback_hours: int) -> list[dict]:
    """Poll all active clusters."""
    clusters = (
        db.query(Cluster)
        .filter(Cluster.status != "removed")
        .all()
    )

    if not clusters:
        logger.warning("No active clusters found — skipping poll")
        return []

    filter_rules = load_active_rules(db)
    results = []

    async with httpx.AsyncClient() as client:
        for cluster in clusters:
            try:
                result = await poll_cluster(
                    cluster=cluster,
                    db=db,
                    lookback_hours=lookback_hours,
                    filter_rules=filter_rules,
                    client=client,
                )
                results.append(result)
            except Exception:
                logger.exception("Poll failed for cluster %s", cluster.name)
                results.append({
                    "cluster": cluster.name,
                    "error": "Poll failed — see logs",
                })

    return results


# --- Helpers ---

def _parse_time(ts_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 timestamp string to datetime."""
    if not ts_str:
        return None
    try:
        # Handle Alertmanager format: "2024-01-01T00:00:00.000Z"
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError) as e:
        logger.warning("Failed to parse timestamp '%s': %s", ts_str, e)
        return None


def _ts_to_datetime(ts: float) -> datetime:
    """Convert Unix timestamp to datetime."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
