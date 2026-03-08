"""DailySection model — one per day within a weekly shift report."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class DailySection(Base):
    __tablename__ = "daily_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shift_reports.id", ondelete="CASCADE"), nullable=False,
    )
    section_date: Mapped[date] = mapped_column(Date, nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    daily_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    report = relationship("ShiftReport", back_populates="daily_sections")
    alert_records = relationship(
        "AlertRecord", back_populates="daily_section", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DailySection(id={self.id}, date={self.section_date})>"
