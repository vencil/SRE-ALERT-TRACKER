"""Tests for admin router — retention config and purge."""

import pytest
from fastapi.testclient import TestClient


class TestRetentionConfig:
    """Test retention configuration endpoints."""

    def test_get_retention_default(self, client: TestClient):
        """Get default retention config (auto-created)."""
        res = client.get("/api/admin/retention")
        assert res.status_code == 200
        data = res.json()
        assert data["retention_months"] == 12
        assert data["purge_cron"] == "0 3 1 * *"

    def test_update_retention(self, client: TestClient):
        """Update retention months."""
        # First create the default
        client.get("/api/admin/retention")

        res = client.patch("/api/admin/retention", json={"retention_months": 6})
        assert res.status_code == 200
        assert res.json()["retention_months"] == 6

    def test_update_retention_invalid(self, client: TestClient):
        """Reject invalid retention months (< 1)."""
        res = client.patch("/api/admin/retention", json={"retention_months": 0})
        assert res.status_code == 422

    def test_update_retention_valid_cron(self, client: TestClient):
        """Accept valid cron expression."""
        client.get("/api/admin/retention")
        res = client.patch("/api/admin/retention", json={"purge_cron": "0 0 1 * *"})
        assert res.status_code == 200
        assert res.json()["purge_cron"] == "0 0 1 * *"

    def test_update_retention_invalid_cron(self, client: TestClient):
        """Reject invalid cron expression."""
        res = client.patch("/api/admin/retention", json={"purge_cron": "invalid cron"})
        assert res.status_code == 422


class TestPurge:
    """Test data purge endpoints."""

    def test_purge_empty_db(self, client: TestClient):
        """Purge on empty database returns zero counts."""
        res = client.post("/api/admin/purge")
        assert res.status_code == 200
        data = res.json()
        assert data["reports_deleted"] == 0
        assert data["sections_deleted"] == 0
        assert data["alerts_deleted"] == 0

    def test_purge_with_custom_months(self, client: TestClient):
        """Purge accepts custom months parameter."""
        res = client.post("/api/admin/purge?months=1")
        assert res.status_code == 200
        assert res.json()["reports_deleted"] == 0
