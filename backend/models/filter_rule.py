"""AlertFilterRule model — whitelist/blacklist rules for alert ingestion."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AlertFilterRule(Base):
    __tablename__ = "alert_filter_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="whitelist | blacklist",
    )
    filter_field: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="alertname | group | severity",
    )
    filter_value: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<AlertFilterRule(id={self.id}, {self.rule_type}:{self.filter_field}={self.filter_value})>"
