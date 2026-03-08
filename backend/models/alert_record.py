"""AlertRecord model — core alert tracking record with M:N label relation."""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# Many-to-Many association table
alert_record_labels = Table(
    "alert_record_labels",
    Base.metadata,
    Column("alert_record_id", Integer, ForeignKey("alert_records.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", Integer, ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class AlertRecord(Base):
    __tablename__ = "alert_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    daily_section_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("daily_sections.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id"), nullable=False, index=True,
    )
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alert_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="warning", index=True)
    instance: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    runbook_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Manual fields (filled by on-call operator)
    phenomenon: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Counters & timestamps
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_firing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_firing_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Flags
    auto_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    manually_edited: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    daily_section = relationship("DailySection", back_populates="alert_records")
    cluster = relationship("Cluster", back_populates="alert_records")
    labels = relationship("Label", secondary=alert_record_labels, back_populates="alert_records")

    def __repr__(self) -> str:
        return f"<AlertRecord(id={self.id}, name='{self.alert_name}', fp='{self.fingerprint[:8]}...')>"
