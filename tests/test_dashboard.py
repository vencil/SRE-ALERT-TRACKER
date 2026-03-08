"""Tests for dashboard API endpoints."""

import pytest


class TestDashboardTrends:
    def test_trends_empty(self, client):
        resp = client.get("/api/dashboard/trends")
        assert resp.status_code == 200
        assert resp.json()["trends"] == []

    def test_trends_with_data(self, client):
        # Create a report + alert to have data
        r = client.post("/api/reports", json={"year": 2026, "week_number": 10})
        report = r.json()
        section_id = report["daily_sections"][0]["id"]

        # Manually insert an alert (via the dedup service or direct)
        # For now just verify the endpoint works with no data for this week
        resp = client.get("/api/dashboard/trends", params={"weeks": 4})
        assert resp.status_code == 200
        assert isinstance(resp.json()["trends"], list)

    def test_trends_with_cluster_filter(self, client):
        resp = client.get("/api/dashboard/trends", params={"cluster_id": 999})
        assert resp.status_code == 200
        assert resp.json()["trends"] == []


class TestDashboardTopAlerts:
    def test_top_alerts_empty(self, client):
        resp = client.get("/api/dashboard/top-alerts")
        assert resp.status_code == 200
        assert resp.json()["top_alerts"] == []

    def test_top_alerts_with_params(self, client):
        resp = client.get("/api/dashboard/top-alerts", params={"n": 5, "weeks": 2})
        assert resp.status_code == 200
        assert isinstance(resp.json()["top_alerts"], list)


class TestSeverityDistribution:
    def test_severity_distribution_empty(self, client):
        resp = client.get("/api/dashboard/severity-distribution")
        assert resp.status_code == 200
        assert resp.json()["distribution"] == []
