"""Weekly task Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    is_active: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    sort_order: int = 0


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class TaskAssignmentOut(BaseModel):
    task_id: int
    task_title: str
    is_checked: bool
    checked_by: Optional[str] = None
    checked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TaskCheckToggle(BaseModel):
    is_checked: bool
    checked_by: Optional[str] = None


class TaskListResponse(BaseModel):
    tasks: list[TaskOut]
