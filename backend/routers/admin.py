"""Admin router — retention config and data purge management.

Requires admin-level access in production (AT_ADMIN_USERS).
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from config import AuthMode, settings
from database import get_db
from services.retention_manager import get_retention_config, purge_old_data

logger = logging.getLogger("alert-tracker.admin")

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def require_admin(request: Request) -> str:
    """Dependency that enforces admin-level access.

    - AUTH_MODE=none (lab): all users are allowed.
    - AUTH_MODE=oauth2-proxy + AT_ADMIN_USERS empty: all authenticated users allowed.
    - AUTH_MODE=oauth2-proxy + AT_ADMIN_USERS set: only listed users allowed.
    """
    user = getattr(request.state, "user", "")
    if settings.auth_mode == AuthMode.NONE:
        return user

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    admin_list = [u.strip() for u in settings.admin_users.split(",") if u.strip()]
    if admin_list and user not in admin_list:
        logger.warning("Admin access denied for user '%s' on %s", user, request.url.path)
        raise HTTPException(status_code=403, detail="Admin access required")

    return user

# Simple cron expression pattern: 5 fields (minute hour dom month dow)
_CRON_FIELD = r"(\*|[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*(/[0-9]+)?)"
_CRON_RE = re.compile(rf"^{_CRON_FIELD}(\s+{_CRON_FIELD}){{4}}$")


class RetentionOut(BaseModel):
    retention_months: int
    purge_cron: str
    last_purge_at: str | None = None

    model_config = {"from_attributes": True}


class RetentionUpdate(BaseModel):
    retention_months: int | None = Field(None, ge=1, le=60)
    purge_cron: str | None = None

    @field_validator("purge_cron")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _CRON_RE.match(v.strip()):
            raise ValueError("Invalid cron expression — expected 5 fields: minute hour dom month dow")
        return v.strip()


class PurgeResult(BaseModel):
    reports_deleted: int
    sections_deleted: int
    alerts_deleted: int


@router.get("/retention", response_model=RetentionOut)
def get_retention(db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Get current retention configuration."""
    config = get_retention_config(db)
    return RetentionOut(
        retention_months=config.retention_months,
        purge_cron=config.purge_cron,
        last_purge_at=str(config.last_purge_at) if config.last_purge_at else None,
    )


@router.patch("/retention", response_model=RetentionOut)
def update_retention(data: RetentionUpdate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Update retention configuration."""
    config = get_retention_config(db)
    if data.retention_months is not None:
        config.retention_months = data.retention_months
    if data.purge_cron is not None:
        config.purge_cron = data.purge_cron
    db.commit()
    db.refresh(config)
    return RetentionOut(
        retention_months=config.retention_months,
        purge_cron=config.purge_cron,
        last_purge_at=str(config.last_purge_at) if config.last_purge_at else None,
    )


@router.post("/purge", response_model=PurgeResult)
def trigger_purge(
    months: int | None = None,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Manually trigger data purge. Uses configured retention_months if not specified."""
    result = purge_old_data(db, retention_months=months)
    return PurgeResult(**result)
