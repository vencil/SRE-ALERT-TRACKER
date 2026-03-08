"""Cluster model — monitoring source definitions synced from clusters.yaml."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    prometheus_url: Mapped[str] = mapped_column(Text, nullable=False)
    alertmanager_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="unknown",
        comment="healthy | unhealthy | unknown | removed",
    )
    interval_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pull_info: Mapped[bool] = mapped_column(Boolean, default=False)
    instance_label: Mapped[str] = mapped_column(String(100), default="instance")
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    # Relationships
    alert_records = relationship("AlertRecord", back_populates="cluster")
    maintenance_windows = relationship("MaintenanceWindow", back_populates="cluster")
    poller_config = relationship("PollerConfig", back_populates="cluster", uselist=False)

    def __repr__(self) -> str:
        return f"<Cluster(id={self.id}, name='{self.name}', status='{self.status}')>"
