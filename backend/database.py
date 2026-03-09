"""SQLAlchemy engine + session factory — supports SQLite and MariaDB."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


class Base(DeclarativeBase):
    """ORM base class for all models."""
    pass


def _build_engine():
    url = settings.effective_database_url
    kwargs = {}
    if settings.is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, echo=False, **kwargs)


engine = _build_engine()

# Enable WAL mode for SQLite (better concurrent read performance)
if settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (called at startup).

    For SQLite, ensures the parent directory exists before creating tables.
    This is the only place that creates the data directory — config.py
    intentionally avoids mkdir to prevent PermissionError on import.
    """
    if settings.is_sqlite:
        db_path = Path(settings.data_dir)
        db_path.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
