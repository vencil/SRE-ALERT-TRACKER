"""Tests for Markdown export and the export router ?format=md."""

import os
from datetime import date, datetime

import pytest

os.environ.setdefault("TESTING", "1")

from models.cluster import Cluster
from models.shift_report import ShiftReport
from models.daily_section import DailySection
from models.alert_record import AlertRecord


def _seed_report(db_session):
    """Create a report with one section and one alert."""
    cluster = Cluster(name="test-cluster", prometheus_url="http://p:9090", alertmanager_url="http://a:9093")
    db_session.add(cluster)
    db_session.flush()

    report = ShiftReport(year=2026, week_number=11, operator_name="poyu")
    db_session.add(report)
    db_session.flush()

    section = DailySection(report_id=report.id, section_date=date(2026, 3, 9))
    db_session.add(section)
    db_session.flush()

    alert = AlertRecord(
        daily_section_id=section.id,
        cluster_id=cluster.id,
        fingerprint="abc123",
        alert_name="TestHighCPU",
        severity="critical",
        instance="pod-01",
        occurrence_count=5,
        first_firing_at=datetime(2026, 3, 9, 8, 0, 0),
        last_firing_at=datetime(2026, 3, 9, 14, 0, 0),
        phenomenon="CPU 使用率超過 90%",
        impact="服務回應變慢",
        action_taken=None,
        auto_resolved=False,
    )
    db_session.add(alert)
    db_session.commit()
    return report


class TestMarkdownExportRoute:
    def test_export_md_returns_markdown(self, client, db_session):
        report = _seed_report(db_session)
        resp = client.get(f"/api/export/report/{report.id}?format=md")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert resp.headers["content-disposition"].endswith('.md"')

    def test_export_md_contains_report_heading(self, client, db_session):
        report = _seed_report(db_session)
        resp = client.get(f"/api/export/report/{report.id}?format=md")
        body = resp.text
        assert "# 週報 2026-W11" in body
        assert "poyu" in body

    def test_export_md_contains_alert_data(self, client, db_session):
        report = _seed_report(db_session)
        resp = client.get(f"/api/export/report/{report.id}?format=md")
        body = resp.text
        assert "TestHighCPU" in body
        assert "critical" in body
        assert "CPU 使用率超過 90%" in body

    def test_export_md_not_found(self, client, db_session):
        resp = client.get("/api/export/report/9999?format=md")
        assert resp.status_code == 404

    def test_export_invalid_format_rejected(self, client, db_session):
        report = _seed_report(db_session)
        resp = client.get(f"/api/export/report/{report.id}?format=xml")
        assert resp.status_code == 422


class TestMarkdownExportService:
    def test_empty_report_returns_empty(self, db_session):
        from services.export_service import export_report_markdown
        result = export_report_markdown(db_session, 9999)
        assert result == ""

    def test_report_with_no_alerts(self, db_session):
        from services.export_service import export_report_markdown

        report = ShiftReport(year=2026, week_number=12, operator_name="test")
        db_session.add(report)
        db_session.flush()
        section = DailySection(report_id=report.id, section_date=date(2026, 3, 16))
        db_session.add(section)
        db_session.commit()

        result = export_report_markdown(db_session, report.id)
        assert "# 週報 2026-W12" in result
        assert "*No alerts.*" in result
