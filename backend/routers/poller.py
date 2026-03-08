"""Poller router — status check and manual trigger for alert polling."""

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from services.alert_poller import poll_all_clusters

router = APIRouter(prefix="/api/poller", tags=["Poller"])


# In-memory poller state (updated by scheduler and manual triggers)
_poller_state = {
    "last_run_at": None,
    "last_run_status": "never_run",
    "last_results": [],
    "is_running": False,
}
_poller_lock = asyncio.Lock()


@router.get("/status")
def poller_status():
    """Get current poller status and configuration."""
    return {
        "interval_hours": settings.poller_interval_hours,
        "lookback_hours": settings.poller_lookback_hours,
        "last_run_at": _poller_state["last_run_at"],
        "last_run_status": _poller_state["last_run_status"],
        "is_running": _poller_state["is_running"],
        "last_results": _poller_state["last_results"],
    }


@router.post("/trigger")
async def trigger_poll(db: Session = Depends(get_db)):
    """Manually trigger an alert poll across all clusters."""
    async with _poller_lock:
        if _poller_state["is_running"]:
            return {"message": "Poller is already running", "status": "skipped"}
        _poller_state["is_running"] = True

    try:
        results = await poll_all_clusters(
            db=db,
            interval_hours=settings.poller_interval_hours,
            lookback_hours=settings.poller_lookback_hours,
        )
        _poller_state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        _poller_state["last_run_status"] = "success"
        _poller_state["last_results"] = results
        return {"message": "Poll completed", "results": results}
    except Exception:
        _poller_state["last_run_status"] = "error"
        raise
    finally:
        _poller_state["is_running"] = False
