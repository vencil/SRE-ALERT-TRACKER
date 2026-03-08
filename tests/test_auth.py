"""Tests for auth middleware."""

import os

import pytest
from fastapi.testclient import TestClient


class TestAuthMiddlewareNoneMode:
    """Test AUTH_MODE=none (default lab mode)."""

    def test_health_no_auth(self, client: TestClient):
        """Health endpoint is always accessible."""
        res = client.get("/api/health")
        assert res.status_code == 200

    def test_me_returns_dev_user(self, client: TestClient):
        """In none mode, /api/me returns dev-user."""
        res = client.get("/api/me")
        assert res.status_code == 200
        data = res.json()
        assert data["user"] == "dev-user"
        assert data["auth_mode"] == "none"

    def test_get_request_works(self, client: TestClient):
        """GET requests work in none mode."""
        res = client.get("/api/reports")
        assert res.status_code == 200

    def test_post_request_works(self, client: TestClient):
        """POST requests work in none mode."""
        res = client.post("/api/labels", json={"name": "auth-test-label"})
        assert res.status_code == 201
