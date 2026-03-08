"""RetentionConfig model — data retention and purge schedule settings."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RetentionConfig(Base):
    __tablename__ = "retention_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    retention_months: Mapped[int] = mapped_column(Integer, default=12)
    purge_cron: Mapped[str] = mapped_column(String(100), default="0 3 1 * *")
    last_purge_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<RetentionConfig(id={self.id}, months={self.retention_months})>"
