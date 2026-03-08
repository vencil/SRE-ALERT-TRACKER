"""Maintenance window Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class MaintenanceWindowOut(BaseModel):
    id: int
    cluster_id: int
    cluster_name: Optional[str] = None
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MaintenanceWindowCreate(BaseModel):
    cluster_id: int
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = Field(default=None, max_length=2000)
    created_by: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class MaintenanceWindowUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: Optional[str] = Field(default=None, max_length=2000)


class MaintenanceWindowListResponse(BaseModel):
    windows: list[MaintenanceWindowOut]
