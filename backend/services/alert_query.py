"""Shared alert query builder — used by alerts router and export router."""

from typing import Optional

from sqlalchemy.orm import Query

from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.label import Label
from models.shift_report import ShiftReport


def apply_alert_filters(
    query: Query,
    *,
    cluster_id: Optional[int] = None,
    severity: Optional[str] = None,
    label_id: Optional[int] = None,
    year: Optional[int] = None,
    week: Optional[int] = None,
) -> Query:
    """Apply common alert filters (cluster, severity, label, year/week)."""
    if cluster_id is not None:
        query = query.filter(AlertRecord.cluster_id == cluster_id)
    if severity is not None:
        query = query.filter(AlertRecord.severity == severity)
    if label_id is not None:
        query = query.filter(AlertRecord.labels.any(Label.id == label_id))
    if year is not None or week is not None:
        query = query.join(DailySection).join(ShiftReport)
        if year is not None:
            query = query.filter(ShiftReport.year == year)
        if week is not None:
            query = query.filter(ShiftReport.week_number == week)
    return query
