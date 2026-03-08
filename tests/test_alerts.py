"""Tests for Alerts API (query, update, label management)."""

from models.alert_record import AlertRecord
from models.cluster import Cluster
from models.label import Label


def _seed_alert(db_session, client):
    """Helper: create a cluster, report, and alert for testing."""
    cluster = Cluster(name="test-cluster", prometheus_url="http://prom:9090", alertmanager_url="http://am:9093")
    db_session.add(cluster)
    db_session.commit()

    # Create report (which creates daily sections)
    resp = client.post("/api/reports", json={"year": 2026, "week_number": 10})
    section_id = resp.json()["daily_sections"][0]["id"]

    alert = AlertRecord(
        daily_section_id=section_id,
        cluster_id=cluster.id,
        fingerprint="abc123def456",
        alert_name="TestHighCPU",
        severity="critical",
        instance="pod-123",
        occurrence_count=5,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert, cluster


class TestAlertsCRUD:
    def test_list_alerts_empty(self, client):
        resp = client.get("/api/alerts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_alerts(self, client, db_session):
        _seed_alert(db_session, client)
        resp = client.get("/api/alerts")
        data = resp.json()
        assert data["total"] == 1
        assert data["alerts"][0]["alert_name"] == "TestHighCPU"

    def test_get_alert(self, client, db_session):
        alert, _ = _seed_alert(db_session, client)
        resp = client.get(f"/api/alerts/{alert.id}")
        assert resp.status_code == 200
        assert resp.json()["fingerprint"] == "abc123def456"

    def test_get_alert_not_found(self, client):
        resp = client.get("/api/alerts/999")
        assert resp.status_code == 404

    def test_update_alert_manual_fields(self, client, db_session):
        alert, _ = _seed_alert(db_session, client)
        resp = client.patch(f"/api/alerts/{alert.id}", json={
            "phenomenon": "CPU spike on pod-123",
            "impact": "API latency increased",
            "action_taken": "Scaled up replicas",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["phenomenon"] == "CPU spike on pod-123"
        assert data["manually_edited"] is False  # manual fields don't set flag

    def test_update_alert_auto_field_sets_flag(self, client, db_session):
        alert, _ = _seed_alert(db_session, client)
        resp = client.patch(f"/api/alerts/{alert.id}", json={
            "alert_name": "OverriddenName",
        })
        assert resp.status_code == 200
        assert resp.json()["manually_edited"] is True

    def test_filter_by_severity(self, client, db_session):
        _seed_alert(db_session, client)
        resp = client.get("/api/alerts?severity=critical")
        assert resp.json()["total"] == 1

        resp = client.get("/api/alerts?severity=warning")
        assert resp.json()["total"] == 0


class TestAlertLabels:
    def test_add_label_to_alert(self, client, db_session):
        alert, _ = _seed_alert(db_session, client)

        # Create label
        label = Label(name="database")
        db_session.add(label)
        db_session.commit()

        resp = client.post(f"/api/alerts/{alert.id}/labels", json={"label_id": label.id})
        assert resp.status_code == 200
        assert len(resp.json()["labels"]) == 1
        assert resp.json()["labels"][0]["name"] == "database"

    def test_remove_label_from_alert(self, client, db_session):
        alert, _ = _seed_alert(db_session, client)

        label = Label(name="database")
        db_session.add(label)
        db_session.commit()

        # Add then remove
        client.post(f"/api/alerts/{alert.id}/labels", json={"label_id": label.id})
        resp = client.delete(f"/api/alerts/{alert.id}/labels/{label.id}")
        assert resp.status_code == 200
        assert len(resp.json()["labels"]) == 0

    def test_add_nonexistent_label_fails(self, client, db_session):
        alert, _ = _seed_alert(db_session, client)
        resp = client.post(f"/api/alerts/{alert.id}/labels", json={"label_id": 999})
        assert resp.status_code == 404

    def test_list_alerts_with_multiple_labels_no_duplicates(self, client, db_session):
        """Ensure alerts with multiple labels don't produce duplicate rows in list."""
        alert, _ = _seed_alert(db_session, client)

        # Add multiple labels
        for name in ["db", "network", "urgent"]:
            label = Label(name=name)
            db_session.add(label)
            db_session.commit()
            client.post(f"/api/alerts/{alert.id}/labels", json={"label_id": label.id})

        resp = client.get("/api/alerts")
        data = resp.json()
        assert data["total"] == 1
        assert len(data["alerts"]) == 1
        assert len(data["alerts"][0]["labels"]) == 3
