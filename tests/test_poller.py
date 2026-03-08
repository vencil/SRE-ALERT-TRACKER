"""Tests for Alert Poller — merge logic and router endpoints."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from services.alert_poller import merge_alerts


class TestMergeAlerts:
    def test_am_preferred_over_pm(self):
        am = [{"fingerprint": "fp1", "alertname": "Alert1", "source": "alertmanager", "runbook_url": "http://run"}]
        pm = [{"fingerprint": "fp1", "alertname": "Alert1", "source": "prometheus", "runbook_url": ""}]

        merged = merge_alerts(am, pm)
        assert len(merged) == 1
        assert merged[0]["source"] == "alertmanager"
        assert merged[0]["runbook_url"] == "http://run"

    def test_pm_supplements_missing(self):
        am = [{"fingerprint": "fp1", "alertname": "Alert1", "source": "alertmanager"}]
        pm = [{"fingerprint": "fp2", "alertname": "Alert2", "source": "prometheus"}]

        merged = merge_alerts(am, pm)
        assert len(merged) == 2

    def test_empty_both(self):
        assert merge_alerts([], []) == []

    def test_am_only(self):
        am = [{"fingerprint": "fp1", "alertname": "A", "source": "am"}]
        merged = merge_alerts(am, [])
        assert len(merged) == 1

    def test_pm_only(self):
        pm = [{"fingerprint": "fp1", "alertname": "A", "source": "pm"}]
        merged = merge_alerts([], pm)
        assert len(merged) == 1


class TestPollerRouter:
    def test_poller_status(self, client):
        resp = client.get("/api/poller/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "interval_hours" in data
        assert "is_running" in data
        assert data["last_run_status"] == "never_run"

    def test_trigger_poll_no_clusters(self, client):
        """Trigger poll with no clusters — should succeed with empty results."""
        resp = client.post("/api/poller/trigger")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
