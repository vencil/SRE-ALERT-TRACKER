"""Unit tests for the Lab-only test seed endpoint."""

from datetime import date


def test_seed_creates_report_and_alerts(client):
    """POST /api/test/seed creates a report with alerts."""
    today = date.today()
    resp = client.post("/api/test/seed", json={
        "cluster_name": "test-cluster",
        "target_date": today.isoformat(),
        "alerts": [
            {"alert_name": "TestAlert1", "severity": "critical"},
            {"alert_name": "TestAlert2", "severity": "warning"},
        ],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["alert_count"] == 2
    assert len(data["alert_ids"]) == 2
    assert data["section_date"] == today.isoformat()

    # Verify alerts exist via API
    report_id = data["report_id"]
    report_resp = client.get(f"/api/reports/{report_id}")
    assert report_resp.status_code == 200


def test_seed_auto_creates_cluster(client):
    """POST /api/test/seed creates a cluster if it doesn't exist."""
    resp = client.post("/api/test/seed", json={
        "cluster_name": "auto-created-cluster",
        "alerts": [{"alert_name": "A1", "severity": "info"}],
    })
    assert resp.status_code == 200

    # Verify cluster exists via clusters API
    clusters_resp = client.get("/api/clusters")
    assert clusters_resp.status_code == 200
    data = clusters_resp.json()
    # Handle both list and paginated response formats
    items = data if isinstance(data, list) else data.get("items", data.get("clusters", []))
    names = [c["name"] for c in items]
    assert "auto-created-cluster" in names


def test_seed_default_date_is_today(client):
    """POST /api/test/seed without target_date uses today."""
    today = date.today()
    resp = client.post("/api/test/seed", json={
        "cluster_name": "default-date-cluster",
        "alerts": [{"alert_name": "A1"}],
    })
    assert resp.status_code == 200
    assert resp.json()["section_date"] == today.isoformat()


def test_seed_empty_alerts(client):
    """POST /api/test/seed with no alerts creates report but no alerts."""
    resp = client.post("/api/test/seed", json={
        "cluster_name": "empty-cluster",
        "alerts": [],
    })
    assert resp.status_code == 200
    assert resp.json()["alert_count"] == 0
    assert resp.json()["alert_ids"] == []
