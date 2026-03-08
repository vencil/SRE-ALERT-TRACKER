"""Tests for export API endpoints."""

import pytest


class TestExportReport:
    def test_export_report_csv(self, client):
        r = client.post("/api/reports", json={"year": 2026, "week_number": 10})
        report_id = r.json()["id"]

        resp = client.get(f"/api/export/report/{report_id}", params={"format": "csv"})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_report_json(self, client):
        r = client.post("/api/reports", json={"year": 2026, "week_number": 11})
        report_id = r.json()["id"]

        resp = client.get(f"/api/export/report/{report_id}", params={"format": "json"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    def test_export_report_not_found(self, client):
        resp = client.get("/api/export/report/9999")
        assert resp.status_code == 404

    def test_export_report_invalid_format(self, client):
        r = client.post("/api/reports", json={"year": 2026, "week_number": 12})
        report_id = r.json()["id"]
        resp = client.get(f"/api/export/report/{report_id}", params={"format": "xml"})
        assert resp.status_code == 422


class TestExportAlerts:
    def test_export_alerts_csv(self, client):
        resp = client.get("/api/export/alerts")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_export_alerts_with_filters(self, client):
        resp = client.get("/api/export/alerts", params={"severity": "critical"})
        assert resp.status_code == 200
