"""ShiftReport + DailySection Pydantic schemas."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.alert import AlertOut


class DailySectionOut(BaseModel):
    id: int
    report_id: int
    section_date: date
    operator_name: Optional[str] = None
    daily_notes: Optional[str] = None
    alert_count: int = 0
    alerts: list[AlertOut] = []

    model_config = {"from_attributes": True}


class ReportSummary(BaseModel):
    id: int
    year: int
    week_number: int
    operator_name: Optional[str] = None
    total_alerts: int = 0
    filled_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportDetail(BaseModel):
    id: int
    year: int
    week_number: int
    operator_name: Optional[str] = None
    notes: Optional[str] = None
    daily_sections: list[DailySectionOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportCreate(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    week_number: int = Field(..., ge=1, le=53)
    operator_name: Optional[str] = None


class ReportUpdate(BaseModel):
    operator_name: Optional[str] = None
    notes: Optional[str] = None


class ReportListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    reports: list[ReportSummary]


class DailySectionUpdate(BaseModel):
    operator_name: Optional[str] = None
    daily_notes: Optional[str] = None
