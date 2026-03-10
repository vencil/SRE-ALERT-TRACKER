"""Tests for AI Suggestion API (POST /api/alerts/{id}/suggest)."""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from models.alert_record import AlertRecord
from models.cluster import Cluster
from models.daily_section import DailySection
from models.shift_report import ShiftReport


def _seed_alert_with_history(db_session):
    """Create an alert with historical records for suggestion testing."""
    cluster = Cluster(name="prod", prometheus_url="", alertmanager_url="")
    db_session.add(cluster)
    db_session.flush()

    # Week 10 — historical record with action_taken
    report_w10 = ShiftReport(year=2026, week_number=10, operator_name="alice")
    db_session.add(report_w10)
    db_session.flush()
    section_w10 = DailySection(report_id=report_w10.id, section_date=date(2026, 3, 2))
    db_session.add(section_w10)
    db_session.flush()

    old = AlertRecord(
        daily_section_id=section_w10.id, cluster_id=cluster.id,
        fingerprint="fp_123", alert_name="HighCPU", severity="critical",
        occurrence_count=5, action_taken="Scaled replicas",
        phenomenon="CPU spike", impact="Latency increased",
        first_firing_at=datetime(2026, 3, 2, 8, 0),
        last_firing_at=datetime(2026, 3, 2, 8, 30),
    )
    db_session.add(old)

    # Week 11 — current alert (no action_taken yet)
    report_w11 = ShiftReport(year=2026, week_number=11)
    db_session.add(report_w11)
    db_session.flush()
    section_w11 = DailySection(report_id=report_w11.id, section_date=date(2026, 3, 9))
    db_session.add(section_w11)
    db_session.flush()

    current = AlertRecord(
        daily_section_id=section_w11.id, cluster_id=cluster.id,
        fingerprint="fp_123", alert_name="HighCPU", severity="critical",
        instance="pod-1", occurrence_count=3,
        first_firing_at=datetime(2026, 3, 9, 14, 0),
        last_firing_at=datetime(2026, 3, 9, 14, 45),
    )
    db_session.add(current)
    db_session.commit()
    db_session.refresh(current)
    return current


class TestSuggestEndpoint:
    def test_suggest_returns_501_when_llm_disabled(self, client, db_session):
        """When LLM is not configured, endpoint returns 501."""
        alert = _seed_alert_with_history(db_session)
        resp = client.post(f"/api/alerts/{alert.id}/suggest")
        assert resp.status_code == 501
        assert "not enabled" in resp.json()["detail"]

    def test_suggest_not_found(self, client):
        """Nonexistent alert returns 404."""
        # First enable LLM to bypass the 501 check
        with patch("routers.alerts.settings") as mock_settings:
            mock_settings.llm_enabled = True
            resp = client.post("/api/alerts/99999/suggest")
            assert resp.status_code == 404

    def test_suggest_success(self, client, db_session):
        """Successful suggestion with mocked LLM service."""
        alert = _seed_alert_with_history(db_session)

        mock_generate = AsyncMock(return_value="建議：檢查 CPU 使用率，考慮擴容 replica。")
        with patch("config.settings.llm_provider", "openai"), \
             patch("config.settings.llm_api_key", "test-key"), \
             patch("services.llm_service.generate_suggestion", new=mock_generate):
            resp = client.post(f"/api/alerts/{alert.id}/suggest")

        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_id"] == alert.id
        assert data["suggestion"] == "建議：檢查 CPU 使用率，考慮擴容 replica。"
        assert data["history_count"] == 1  # One historical record with action_taken

    def test_suggest_disabled_by_default(self, client, db_session):
        """Default config (AT_LLM_PROVIDER=none) should return 501."""
        alert = _seed_alert_with_history(db_session)
        resp = client.post(f"/api/alerts/{alert.id}/suggest")
        assert resp.status_code == 501
