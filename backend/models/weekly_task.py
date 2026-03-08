"""WeeklyTask + ReportTaskAssignment — dynamic on-call checklist items."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class WeeklyTask(Base):
    __tablename__ = "weekly_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )

    # Relationships
    assignments = relationship("ReportTaskAssignment", back_populates="task")

    def __repr__(self) -> str:
        return f"<WeeklyTask(id={self.id}, title='{self.title}')>"


class ReportTaskAssignment(Base):
    __tablename__ = "report_task_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shift_reports.id", ondelete="CASCADE"), nullable=False,
    )
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("weekly_tasks.id", ondelete="CASCADE"), nullable=False,
    )
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    report = relationship("ShiftReport", back_populates="task_assignments")
    task = relationship("WeeklyTask", back_populates="assignments")

    def __repr__(self) -> str:
        return f"<ReportTaskAssignment(report={self.report_id}, task={self.task_id}, checked={self.is_checked})>"
