"""Tests for Alert History API (GET /api/alerts/{id}/history)."""

from datetime import date, datetime

from models.alert_record import AlertRecord
from models.cluster import Cluster
from models.daily_section import DailySection
from models.shift_report import ShiftReport


def _seed_reports_and_alerts(db_session):
    """Create two weeks of data with overlapping fingerprint/name alerts."""
    cluster = Cluster(name="prod-cluster", prometheus_url="http://prom:9090", alertmanager_url="http://am:9093")
    db_session.add(cluster)
    db_session.flush()

    # Week 10 report + section
    report_w10 = ShiftReport(year=2026, week_number=10, operator_name="alice")
    db_session.add(report_w10)
    db_session.flush()
    section_w10 = DailySection(report_id=report_w10.id, section_date=date(2026, 3, 2))
    db_session.add(section_w10)
    db_session.flush()

    # Week 11 report + section
    report_w11 = ShiftReport(year=2026, week_number=11, operator_name="bob")
    db_session.add(report_w11)
    db_session.flush()
    section_w11 = DailySection(report_id=report_w11.id, section_date=date(2026, 3, 9))
    db_session.add(section_w11)
    db_session.flush()

    # Alert in week 10 — same fingerprint, with action_taken
    old_alert = AlertRecord(
        daily_section_id=section_w10.id,
        cluster_id=cluster.id,
        fingerprint="fp_same_123",
        alert_name="HighCPU",
        severity="critical",
        instance="pod-1",
        occurrence_count=3,
        action_taken="Scaled replicas to 5",
        phenomenon="CPU > 90% for 10min",
        first_firing_at=datetime(2026, 3, 2, 8, 0),
        last_firing_at=datetime(2026, 3, 2, 8, 30),
    )
    db_session.add(old_alert)

    # Alert in week 10 — same name, different fingerprint, with action_taken
    similar_alert = AlertRecord(
        daily_section_id=section_w10.id,
        cluster_id=cluster.id,
        fingerprint="fp_different_456",
        alert_name="HighCPU",
        severity="warning",
        instance="pod-2",
        occurrence_count=1,
        action_taken="Investigated, was a deploy spike",
        first_firing_at=datetime(2026, 3, 2, 10, 0),
        last_firing_at=datetime(2026, 3, 2, 10, 15),
    )
    db_session.add(similar_alert)

    # Alert in week 10 — same name, no action_taken (should be filtered out)
    no_action_alert = AlertRecord(
        daily_section_id=section_w10.id,
        cluster_id=cluster.id,
        fingerprint="fp_no_action_789",
        alert_name="HighCPU",
        severity="info",
        instance="pod-3",
        occurrence_count=1,
    )
    db_session.add(no_action_alert)

    # Current alert in week 11 — the one we'll query history for
    current_alert = AlertRecord(
        daily_section_id=section_w11.id,
        cluster_id=cluster.id,
        fingerprint="fp_same_123",
        alert_name="HighCPU",
        severity="critical",
        instance="pod-1",
        occurrence_count=7,
        first_firing_at=datetime(2026, 3, 9, 14, 0),
        last_firing_at=datetime(2026, 3, 9, 14, 45),
    )
    db_session.add(current_alert)
    db_session.commit()

    db_session.refresh(old_alert)
    db_session.refresh(similar_alert)
    db_session.refresh(current_alert)
    return current_alert, old_alert, similar_alert


class TestAlertHistory:
    def test_history_fingerprint_first(self, client, db_session):
        """Fingerprint-matched records come first with match_type='fingerprint'."""
        current, old_fp, _ = _seed_reports_and_alerts(db_session)
        resp = client.get(f"/api/alerts/{current.id}/history")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 2
        assert data["alert_name"] == "HighCPU"
        # First record should be fingerprint match
        assert data["records"][0]["match_type"] == "fingerprint"
        assert data["records"][0]["action_taken"] == "Scaled replicas to 5"
        # Second record should be alert_name match
        assert data["records"][1]["match_type"] == "alert_name"

    def test_history_excludes_self(self, client, db_session):
        """Current alert should not appear in its own history."""
        current, _, _ = _seed_reports_and_alerts(db_session)
        resp = client.get(f"/api/alerts/{current.id}/history")
        data = resp.json()
        record_ids = [r["id"] for r in data["records"]]
        assert current.id not in record_ids

    def test_history_excludes_empty_action_taken(self, client, db_session):
        """Records without action_taken should be filtered out."""
        current, _, _ = _seed_reports_and_alerts(db_session)
        resp = client.get(f"/api/alerts/{current.id}/history")
        data = resp.json()
        for record in data["records"]:
            assert record["action_taken"] is not None
            assert record["action_taken"] != ""

    def test_history_empty_for_first_time_alert(self, client, db_session):
        """A brand-new alert with no history should return total=0."""
        cluster = Cluster(name="c1", prometheus_url="", alertmanager_url="")
        db_session.add(cluster)
        db_session.flush()
        report = ShiftReport(year=2026, week_number=12)
        db_session.add(report)
        db_session.flush()
        section = DailySection(report_id=report.id, section_date=date(2026, 3, 16))
        db_session.add(section)
        db_session.flush()

        alert = AlertRecord(
            daily_section_id=section.id,
            cluster_id=cluster.id,
            fingerprint="unique_fp",
            alert_name="NewAlertNeverSeen",
            severity="info",
            occurrence_count=1,
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)

        resp = client.get(f"/api/alerts/{alert.id}/history")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["records"] == []

    def test_history_not_found(self, client):
        """Nonexistent alert ID should return 404."""
        resp = client.get("/api/alerts/99999/history")
        assert resp.status_code == 404

    def test_history_respects_limit(self, client, db_session):
        """Limit parameter should cap the number of returned records."""
        current, _, _ = _seed_reports_and_alerts(db_session)
        resp = client.get(f"/api/alerts/{current.id}/history", params={"limit": 1})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_history_includes_week_info(self, client, db_session):
        """History records should include year, week_number, operator_name."""
        current, _, _ = _seed_reports_and_alerts(db_session)
        resp = client.get(f"/api/alerts/{current.id}/history")
        record = resp.json()["records"][0]
        assert record["year"] == 2026
        assert record["week_number"] == 10
        assert record["operator_name"] == "alice"
        assert record["cluster_name"] == "prod-cluster"
