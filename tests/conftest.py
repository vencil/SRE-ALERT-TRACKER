"""Test fixtures — in-memory SQLite DB + FastAPI TestClient."""

import os
import sys
import tempfile
from pathlib import Path

# Set env vars BEFORE importing backend modules (avoids /data permission error)
import atexit
import shutil

_tmp_dir = tempfile.mkdtemp()
atexit.register(lambda: shutil.rmtree(_tmp_dir, ignore_errors=True))
os.environ.setdefault("AT_DATA_DIR", _tmp_dir)
os.environ.setdefault("AT_CONFIG_DIR", _tmp_dir)
os.environ.setdefault("AT_AUTH_MODE", "none")
os.environ.setdefault("AT_DATABASE_URL", "")
os.environ["TESTING"] = "1"

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite DB for each test.

    Uses StaticPool so all connections share the same in-memory database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with DB dependency override."""
    from fastapi.testclient import TestClient

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
