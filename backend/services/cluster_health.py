"""Cluster health check — probe Prometheus and Alertmanager /-/healthy endpoints."""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from config import settings
from models.cluster import Cluster

logger = logging.getLogger("alert-tracker.health")


async def check_cluster_health(cluster: Cluster, client: httpx.AsyncClient) -> str:
    """Check a single cluster's Prometheus + Alertmanager health.

    Returns: "healthy" | "unhealthy"
    """
    prom_ok = False
    am_ok = False

    # Prometheus health
    try:
        resp = await client.get(
            f"{cluster.prometheus_url.rstrip('/')}/-/healthy",
            timeout=settings.health_check_timeout,
        )
        prom_ok = resp.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.warning("Prometheus health check failed for %s: %s", cluster.name, e)

    # Alertmanager health
    try:
        resp = await client.get(
            f"{cluster.alertmanager_url.rstrip('/')}/-/healthy",
            timeout=settings.health_check_timeout,
        )
        am_ok = resp.status_code == 200
    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.warning("Alertmanager health check failed for %s: %s", cluster.name, e)

    return "healthy" if (prom_ok and am_ok) else "unhealthy"


async def check_all_clusters(db: Session) -> list[dict]:
    """Run health checks on all active clusters, update DB status."""
    clusters = (
        db.query(Cluster)
        .filter(Cluster.status != "removed")
        .all()
    )

    results = []
    async with httpx.AsyncClient() as client:
        for cluster in clusters:
            status = await check_cluster_health(cluster, client)
            cluster.status = status
            cluster.last_health_check = datetime.now(timezone.utc).replace(tzinfo=None)
            results.append({
                "cluster_id": cluster.id,
                "name": cluster.name,
                "status": status,
            })

    db.commit()
    logger.info("Health check complete: %d clusters checked", len(results))
    return results
