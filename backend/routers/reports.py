"""Reports router — CRUD for shift reports and daily sections."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.shift_report import ShiftReport
from schemas.report import (
    DailySectionOut,
    DailySectionUpdate,
    ReportCreate,
    ReportDetail,
    ReportListResponse,
    ReportSummary,
    ReportUpdate,
)

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("", response_model=ReportListResponse)
def list_reports(
    year: Optional[int] = Query(None),
    week: Optional[int] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List shift reports with pagination and optional year/week filter."""
    query = db.query(ShiftReport)
    if year is not None:
        query = query.filter(ShiftReport.year == year)
    if week is not None:
        query = query.filter(ShiftReport.week_number == week)

    total = query.count()
    reports_orm = (
        query.order_by(ShiftReport.year.desc(), ShiftReport.week_number.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Batch aggregation: 2 queries for all reports (avoids N+1 problem)
    report_ids = [r.id for r in reports_orm]
    alert_counts: dict[int, int] = {}
    filled_counts: dict[int, int] = {}
    if report_ids:
        count_rows = (
            db.query(
                DailySection.report_id,
                sa_func.count(AlertRecord.id),
            )
            .join(AlertRecord)
            .filter(DailySection.report_id.in_(report_ids))
            .group_by(DailySection.report_id)
            .all()
        )
        alert_counts = {row[0]: row[1] for row in count_rows}

        filled_rows = (
            db.query(
                DailySection.report_id,
                sa_func.count(AlertRecord.id),
            )
            .join(AlertRecord)
            .filter(
                DailySection.report_id.in_(report_ids),
                AlertRecord.action_taken.isnot(None),
                AlertRecord.action_taken != "",
            )
            .group_by(DailySection.report_id)
            .all()
        )
        filled_counts = {row[0]: row[1] for row in filled_rows}

    summaries = []
    for r in reports_orm:
        summaries.append(
            ReportSummary(
                id=r.id,
                year=r.year,
                week_number=r.week_number,
                operator_name=r.operator_name,
                total_alerts=alert_counts.get(r.id, 0),
                filled_count=filled_counts.get(r.id, 0),
                created_at=r.created_at,
            )
        )

    return ReportListResponse(total=total, offset=offset, limit=limit, reports=summaries)


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: int, db: Session = Depends(get_db)):
    """Get report detail with daily sections and alert records."""
    report = (
        db.query(ShiftReport)
        .options(
            joinedload(ShiftReport.daily_sections)
            .joinedload(DailySection.alert_records)
        )
        .filter(ShiftReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    sections_out = []
    for sec in report.daily_sections:
        sections_out.append(
            DailySectionOut(
                id=sec.id,
                report_id=sec.report_id,
                section_date=sec.section_date,
                operator_name=sec.operator_name,
                daily_notes=sec.daily_notes,
                alert_count=len(sec.alert_records),
                alerts=sec.alert_records,
            )
        )

    return ReportDetail(
        id=report.id,
        year=report.year,
        week_number=report.week_number,
        operator_name=report.operator_name,
        notes=report.notes,
        daily_sections=sections_out,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


@router.post("", response_model=ReportDetail, status_code=201)
def create_report(data: ReportCreate, db: Session = Depends(get_db)):
    """Manually create a shift report (usually auto-generated)."""
    # Validate week number is valid for the given year
    try:
        week_start = date.fromisocalendar(data.year, data.week_number, 1)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid week number {data.week_number} for year {data.year}",
        )

    # Check uniqueness
    existing = (
        db.query(ShiftReport)
        .filter(ShiftReport.year == data.year, ShiftReport.week_number == data.week_number)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Report for this year/week already exists")

    report = ShiftReport(
        year=data.year,
        week_number=data.week_number,
        operator_name=data.operator_name,
    )
    db.add(report)
    db.flush()

    # Create 7 daily sections (Mon-Sun)
    for i in range(7):
        section = DailySection(
            report_id=report.id,
            section_date=week_start + timedelta(days=i),
        )
        db.add(section)

    db.commit()
    db.refresh(report)
    return get_report(report.id, db)


@router.patch("/{report_id}", response_model=ReportDetail)
def update_report(report_id: int, data: ReportUpdate, db: Session = Depends(get_db)):
    """Update report metadata (operator_name, notes)."""
    report = db.query(ShiftReport).filter(ShiftReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(report, key, value)

    db.commit()
    return get_report(report_id, db)


# --- Daily Sections ---

sections_router = APIRouter(prefix="/api/sections", tags=["Daily Sections"])


@sections_router.patch("/{section_id}", response_model=DailySectionOut)
def update_section(section_id: int, data: DailySectionUpdate, db: Session = Depends(get_db)):
    """Update daily section (operator_name, daily_notes)."""
    section = db.query(DailySection).filter(DailySection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(section, key, value)

    db.commit()
    db.refresh(section)
    return DailySectionOut(
        id=section.id,
        report_id=section.report_id,
        section_date=section.section_date,
        operator_name=section.operator_name,
        daily_notes=section.daily_notes,
        alert_count=len(section.alert_records),
        alerts=section.alert_records,
    )
