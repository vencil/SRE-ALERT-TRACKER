"""E2E test fixtures — session-scoped, independent from unit test conftest."""

import os
from datetime import date

import httpx
import pytest
from playwright.sync_api import Page


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the running app. Override via E2E_BASE_URL env var."""
    return os.environ.get("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def app_ready(base_url: str):
    """Check app is reachable; skip entire session if not."""
    try:
        resp = httpx.get(f"{base_url}/api/health", timeout=5)
        resp.raise_for_status()
    except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException):
        pytest.skip(f"App not reachable at {base_url} — start with `make dev`")


@pytest.fixture(scope="session")
def seeded_report(base_url: str, app_ready) -> dict:
    """Seed test data via POST /api/test/seed. Returns report metadata.

    Creates 3 alerts with different severities assigned to today's section.
    """
    today = date.today()
    iso_cal = today.isocalendar()

    payload = {
        "cluster_name": "e2e-test-cluster",
        "target_date": today.isoformat(),
        "alerts": [
            {"alert_name": "HighCPUUsage", "severity": "critical"},
            {"alert_name": "DiskSpaceLow", "severity": "warning"},
            {"alert_name": "PodCrashLoop", "severity": "info"},
        ],
    }

    resp = httpx.post(f"{base_url}/api/test/seed", json=payload, timeout=10)
    if resp.status_code == 404:
        pytest.skip("Seed endpoint not available — is AT_AUTH_MODE=none?")
    resp.raise_for_status()
    data = resp.json()

    return {
        "report_id": data["report_id"],
        "year": data["year"],
        "week_number": data["week_number"],
        "section_date": data["section_date"],
        "alert_count": data["alert_count"],
        "alert_ids": data["alert_ids"],
    }


@pytest.fixture()
def report_page(page: Page, base_url: str, seeded_report: dict) -> Page:
    """Navigate to the seeded report's detail page. Returns the Page."""
    report_id = seeded_report["report_id"]
    page.goto(f"{base_url}/reports/{report_id}")
    # Wait for at least one alert card to render
    page.locator(".alert-card").first.wait_for(state="visible", timeout=10000)
    return page
