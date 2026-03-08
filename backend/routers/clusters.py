"""Clusters router — list cluster definitions and health status."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.cluster import Cluster
from schemas.cluster import ClusterListResponse
from services.cluster_health import check_all_clusters

router = APIRouter(prefix="/api/clusters", tags=["Clusters"])


@router.get("", response_model=ClusterListResponse)
def list_clusters(db: Session = Depends(get_db)):
    """List all clusters with their current health status."""
    clusters = (
        db.query(Cluster)
        .filter(Cluster.status != "removed")
        .order_by(Cluster.name)
        .all()
    )
    return ClusterListResponse(clusters=clusters)


@router.post("/health-check")
async def trigger_health_check(db: Session = Depends(get_db)):
    """Manually trigger health check on all clusters."""
    results = await check_all_clusters(db)
    return {"results": results}
