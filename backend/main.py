"""FastAPI entry point — router registration, DB init, cluster sync, scheduler."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import load_clusters_config, settings
from database import SessionLocal, init_db
from models.cluster import Cluster


def _read_version() -> str:
    """Read version from VERSION file (single source of truth).

    Search order:
      1. Same directory as main.py  (Docker: /app/VERSION)
      2. Parent directory            (Dev: repo_root/VERSION)
    """
    here = Path(__file__).resolve().parent
    for candidate in [here / "VERSION", here.parent / "VERSION"]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()
    return "0.0.0"


APP_VERSION = _read_version()

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("alert-tracker")
scheduler = AsyncIOScheduler()


def sync_clusters_from_config(db_session):
    """Sync clusters.yaml definitions into the DB (add/update, never hard delete)."""
    cluster_defs = load_clusters_config(settings.config_dir)
    if not cluster_defs:
        logger.info("No clusters.yaml found or empty — skipping cluster sync")
        return

    existing = {c.name: c for c in db_session.query(Cluster).all()}

    for cdef in cluster_defs:
        name = cdef["name"]
        if name in existing:
            # Update URLs if changed
            c = existing[name]
            c.prometheus_url = cdef.get("prometheus_url", c.prometheus_url)
            c.alertmanager_url = cdef.get("alertmanager_url", c.alertmanager_url)
            c.interval_hours = cdef.get("interval_hours", c.interval_hours)
            c.pull_info = cdef.get("pull_info", c.pull_info)
            c.instance_label = cdef.get("instance_label", c.instance_label)
            if c.status == "removed":
                c.status = "unknown"
        else:
            new_cluster = Cluster(
                name=name,
                prometheus_url=cdef.get("prometheus_url", ""),
                alertmanager_url=cdef.get("alertmanager_url", ""),
                status="unknown",
                interval_hours=cdef.get("interval_hours"),
                pull_info=cdef.get("pull_info", False),
                instance_label=cdef.get("instance_label", "instance"),
            )
            db_session.add(new_cluster)

    # Mark clusters removed from config (soft delete)
    config_names = {c["name"] for c in cluster_defs}
    for name, cluster in existing.items():
        if name not in config_names and cluster.status != "removed":
            cluster.status = "removed"

    db_session.commit()
    logger.info("Cluster sync complete: %d definitions processed", len(cluster_defs))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup
    logger.info("Starting Alert Tracker — DB: %s", "SQLite" if settings.is_sqlite else "MariaDB")
    init_db()

    db = SessionLocal()
    try:
        sync_clusters_from_config(db)
    except Exception:
        db.rollback()
        logger.exception("Cluster sync failed — continuing startup")
    finally:
        db.close()

    # Start APScheduler (skip in test mode — detected by TESTING env var)
    if not os.environ.get("TESTING"):
        _setup_scheduler()
        scheduler.start()
        logger.info("APScheduler started")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Alert Tracker shutting down")


def _setup_scheduler():
    """Register scheduled jobs: weekly report generation + alert polling."""
    from services.alert_poller import poll_all_clusters
    from services.report_generator import generate_current_week_report

    from services.timezone_utils import get_display_tz
    display_tz = get_display_tz()

    # Weekly report generation — every Monday at 00:00 in display timezone
    def _generate_report_job():
        db = SessionLocal()
        try:
            generate_current_week_report(db)
        except Exception:
            logger.exception("Weekly report generation failed")
        finally:
            db.close()

    scheduler.add_job(
        _generate_report_job,
        "cron",
        day_of_week="mon",
        hour=0,
        minute=0,
        timezone=display_tz,
        id="weekly_report_gen",
        replace_existing=True,
    )

    # Alert polling — every N hours
    async def _poll_job():
        db = SessionLocal()
        try:
            await poll_all_clusters(
                db=db,
                interval_hours=settings.poller_interval_hours,
                lookback_hours=settings.poller_lookback_hours,
            )
        except Exception:
            logger.exception("Scheduled alert poll failed")
        finally:
            db.close()

    scheduler.add_job(
        _poll_job,
        "interval",
        hours=settings.poller_interval_hours,
        next_run_time=datetime.now(display_tz),  # Fire immediately on startup
        id="alert_poller",
        replace_existing=True,
    )
    logger.info(
        "Scheduler configured: report_gen=Mon 00:00, poller=every %dh",
        settings.poller_interval_hours,
    )


app = FastAPI(
    title="SRE Alert Tracking System",
    description="值班 alert 追蹤紀錄系統",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS — Lab 模式允許所有來源 (不帶 credentials)；
# Production 應透過 AT_CORS_ORIGINS 環境變數指定明確來源。
_cors_origins = os.environ.get("AT_CORS_ORIGINS", "").split(",") if os.environ.get("AT_CORS_ORIGINS") else []
if settings.auth_mode == "none":
    # Lab / development: allow all origins, no credentials
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production: explicit origins with credentials (for oauth2-proxy cookies)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins or ["*"],
        allow_credentials=bool(_cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Auth middleware
from middleware.auth import AuthMiddleware  # noqa: E402

app.add_middleware(AuthMiddleware)

# --- Register Routers ---
from routers.reports import router as reports_router, sections_router  # noqa: E402
from routers.alerts import router as alerts_router  # noqa: E402
from routers.labels import router as labels_router  # noqa: E402
from routers.clusters import router as clusters_router  # noqa: E402
from routers.filters import router as filters_router  # noqa: E402
from routers.poller import router as poller_router  # noqa: E402
from routers.dashboard import router as dashboard_router  # noqa: E402
from routers.export import router as export_router  # noqa: E402
from routers.tasks import router as tasks_router, report_tasks_router  # noqa: E402
from routers.maintenance import router as maintenance_router  # noqa: E402
from routers.admin import router as admin_router  # noqa: E402

app.include_router(reports_router)
app.include_router(sections_router)
app.include_router(alerts_router)
app.include_router(labels_router)
app.include_router(clusters_router)
app.include_router(filters_router)
app.include_router(poller_router)
app.include_router(dashboard_router)
app.include_router(export_router)
app.include_router(tasks_router)
app.include_router(report_tasks_router)
app.include_router(maintenance_router)
app.include_router(admin_router)

# Lab-only test seed endpoint (AT_AUTH_MODE=none)
if settings.auth_mode == "none":
    from routers.test_seed import router as test_seed_router  # noqa: E402

    app.include_router(test_seed_router)


@app.get("/api/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/me")
def current_user(request: Request):
    """Return current authenticated user info."""
    return {
        "user": getattr(request.state, "user", "anonymous"),
        "email": getattr(request.state, "email", ""),
        "auth_mode": settings.auth_mode,
        "display_timezone": settings.display_timezone,
    }


# --- Static Files (React frontend) ---
_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.is_dir():
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    # SPA fallback: all non-API routes serve index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — all non-API paths fall through to index.html."""
        file_path = _static_dir / full_path
        if file_path.is_file() and file_path.is_relative_to(_static_dir):
            return FileResponse(file_path)
        # SPA fallback — no-cache to ensure fresh deploys are picked up
        index_file = _static_dir / "index.html"
        if index_file.is_file():
            response = FileResponse(index_file)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response
        return {"error": "Frontend not built — run npm build in frontend/"}
