"""Maintenance windows router — CRUD for scheduled maintenance periods."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models.cluster import Cluster
from models.maintenance_window import MaintenanceWindow
from schemas.maintenance import (
    MaintenanceWindowCreate,
    MaintenanceWindowListResponse,
    MaintenanceWindowOut,
    MaintenanceWindowUpdate,
)

router = APIRouter(prefix="/api/maintenance", tags=["Maintenance"])


@router.get("", response_model=MaintenanceWindowListResponse)
def list_maintenance_windows(
    cluster_id: int | None = None,
    db: Session = Depends(get_db),
):
    """List all maintenance windows, optionally filtered by cluster."""
    query = db.query(MaintenanceWindow).options(joinedload(MaintenanceWindow.cluster))
    if cluster_id is not None:
        query = query.filter(MaintenanceWindow.cluster_id == cluster_id)

    windows = query.order_by(MaintenanceWindow.start_time.desc()).all()

    result = []
    for w in windows:
        out = MaintenanceWindowOut.model_validate(w)
        out.cluster_name = w.cluster.name if w.cluster else None
        result.append(out)

    return MaintenanceWindowListResponse(windows=result)


@router.post("", response_model=MaintenanceWindowOut, status_code=201)
def create_maintenance_window(data: MaintenanceWindowCreate, db: Session = Depends(get_db)):
    """Create a new maintenance window."""
    cluster = db.query(Cluster).filter(Cluster.id == data.cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    window = MaintenanceWindow(**data.model_dump())
    db.add(window)
    db.commit()
    db.refresh(window)

    out = MaintenanceWindowOut.model_validate(window)
    out.cluster_name = cluster.name
    return out


@router.patch("/{window_id}", response_model=MaintenanceWindowOut)
def update_maintenance_window(
    window_id: int,
    data: MaintenanceWindowUpdate,
    db: Session = Depends(get_db),
):
    """Update a maintenance window."""
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    update_data = data.model_dump(exclude_unset=True)

    # Pre-validate time range with proposed values
    new_start = update_data.get("start_time", window.start_time)
    new_end = update_data.get("end_time", window.end_time)
    if new_end <= new_start:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    for key, value in update_data.items():
        setattr(window, key, value)

    db.commit()
    db.refresh(window)

    out = MaintenanceWindowOut.model_validate(window)
    out.cluster_name = window.cluster.name if window.cluster else None
    return out


@router.delete("/{window_id}", status_code=204)
def delete_maintenance_window(window_id: int, db: Session = Depends(get_db)):
    """Delete a maintenance window."""
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    db.delete(window)
    db.commit()
    return None
