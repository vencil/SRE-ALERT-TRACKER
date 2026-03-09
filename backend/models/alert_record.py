"""AlertRecord model — core alert tracking record with M:N label relation."""

import json as _json
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from database import Base


class JSONText(TypeDecorator):
    """Store JSON as TEXT — portable across SQLite and MariaDB.

    SQLite has no native JSON type; MariaDB's JSON is essentially LONGTEXT.
    Using Text guarantees compatibility for both backends.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return _json.dumps(value, ensure_ascii=False)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return _json.loads(value)
        return None

# Many-to-Many association table
alert_record_labels = Table(
    "alert_record_labels",
    Base.metadata,
    Column("alert_record_id", Integer, ForeignKey("alert_records.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", Integer, ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True),
)


class AlertRecord(Base):
    __tablename__ = "alert_records"
    __table_args__ = (
        UniqueConstraint("daily_section_id", "fingerprint", name="uq_section_fingerprint"),
    )

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

    # Raw Prometheus/Alertmanager data (preserved for dynamic fields)
    raw_labels: Mapped[dict | None] = mapped_column(JSONText, nullable=True)
    raw_annotations: Mapped[dict | None] = mapped_column(JSONText, nullable=True)

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
