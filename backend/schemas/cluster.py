"""Cluster Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ClusterOut(BaseModel):
    id: int
    name: str
    prometheus_url: str
    alertmanager_url: str
    status: str
    last_health_check: Optional[datetime] = None
    interval_hours: Optional[int] = None
    pull_info: bool = False
    instance_label: str = "instance"

    model_config = {"from_attributes": True}


class ClusterListResponse(BaseModel):
    clusters: list[ClusterOut]
