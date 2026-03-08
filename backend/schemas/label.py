"""Label Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LabelOut(BaseModel):
    id: int
    name: str
    color: Optional[str] = "#6b7280"
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


def _validate_hex_color(v: str | None) -> str | None:
    """Validate hex color format (#RRGGBB)."""
    if v is None:
        return v
    import re
    if not re.match(r"^#[0-9a-fA-F]{6}$", v):
        raise ValueError("Color must be a hex color string like #RRGGBB")
    return v


class LabelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = "#6b7280"
    description: Optional[str] = Field(default=None, max_length=500)

    _validate_color = field_validator("color")(_validate_hex_color)


class LabelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    color: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None

    _validate_color = field_validator("color")(_validate_hex_color)


class LabelMerge(BaseModel):
    source_id: int
    target_id: int


class LabelListResponse(BaseModel):
    labels: list[LabelOut]
