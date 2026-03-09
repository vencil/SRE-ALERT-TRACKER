"""AlertRecord Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from schemas.label import LabelOut


class AlertOut(BaseModel):
    id: int
    daily_section_id: int
    cluster_id: int
    fingerprint: str
    alert_name: str
    severity: str
    instance: Optional[str] = None
    source_group: Optional[str] = None
    runbook_url: Optional[str] = None
    raw_labels: Optional[dict[str, Any]] = None
    raw_annotations: Optional[dict[str, Any]] = None
    phenomenon: Optional[str] = None
    impact: Optional[str] = None
    action_taken: Optional[str] = None
    occurrence_count: int
    first_firing_at: Optional[datetime] = None
    last_firing_at: Optional[datetime] = None
    auto_resolved: bool
    manually_edited: bool
    labels: list[LabelOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    phenomenon: Optional[str] = Field(default=None, max_length=10000)
    impact: Optional[str] = Field(default=None, max_length=10000)
    action_taken: Optional[str] = Field(default=None, max_length=10000)
    # Escape-hatch overrides
    alert_name: Optional[str] = Field(default=None, max_length=255)
    severity: Optional[str] = Field(default=None, max_length=50)
    instance: Optional[str] = Field(default=None, max_length=500)


class AlertListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    alerts: list[AlertOut]


class AlertLabelAction(BaseModel):
    label_id: int
