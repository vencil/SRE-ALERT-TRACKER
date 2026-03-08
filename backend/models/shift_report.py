"""ShiftReport model — weekly report framework auto-generated every Monday."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ShiftReport(Base):
    __tablename__ = "shift_reports"
    __table_args__ = (
        UniqueConstraint("year", "week_number", name="uq_year_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    daily_sections = relationship(
        "DailySection", back_populates="report", cascade="all, delete-orphan",
        order_by="DailySection.section_date",
    )
    task_assignments = relationship(
        "ReportTaskAssignment", back_populates="report", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ShiftReport(id={self.id}, {self.year}-W{self.week_number:02d})>"
