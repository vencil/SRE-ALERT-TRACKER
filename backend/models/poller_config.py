"""PollerConfig model — per-cluster poller scheduling settings."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PollerConfig(Base):
    __tablename__ = "poller_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id"), unique=True, nullable=False,
    )
    interval_hours: Mapped[int] = mapped_column(Integer, default=8)
    lookback_hours: Mapped[int] = mapped_column(Integer, default=12)
    pull_info_severity: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="success | error | running",
    )

    # Relationships
    cluster = relationship("Cluster", back_populates="poller_config")

    def __repr__(self) -> str:
        return f"<PollerConfig(id={self.id}, cluster={self.cluster_id})>"
