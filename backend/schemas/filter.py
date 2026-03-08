"""AlertFilterRule Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FilterRuleOut(BaseModel):
    id: int
    rule_type: str
    filter_field: str
    filter_value: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class FilterRuleCreate(BaseModel):
    rule_type: str = Field(..., pattern="^(whitelist|blacklist)$")
    filter_field: str = Field(..., pattern="^(alertname|group|severity)$")
    filter_value: str = Field(..., min_length=1, max_length=500)
    is_active: bool = True


class FilterRuleListResponse(BaseModel):
    filters: list[FilterRuleOut]
