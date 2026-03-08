"""Tests for maintenance window API endpoints."""

import pytest


class TestMaintenanceWindowsCRUD:
    def _create_cluster(self, client):
        """Helper to get a cluster ID (from DB seed or create)."""
        resp = client.get("/api/clusters")
        clusters = resp.json().get("clusters", [])
        if clusters:
            return clusters[0]["id"]
        # No clusters from config — skip
        return None

    def test_list_empty(self, client):
        resp = client.get("/api/maintenance")
        assert resp.status_code == 200
        assert resp.json()["windows"] == []

    def test_create_maintenance_window(self, client):
        cluster_id = self._create_cluster(client)
        if cluster_id is None:
            pytest.skip("No clusters available")

        resp = client.post("/api/maintenance", json={
            "cluster_id": cluster_id,
            "start_time": "2026-03-08T00:00:00",
            "end_time": "2026-03-08T06:00:00",
            "reason": "Scheduled DB upgrade",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["reason"] == "Scheduled DB upgrade"
        assert data["cluster_id"] == cluster_id

    def test_create_invalid_time_range(self, client):
        cluster_id = self._create_cluster(client)
        if cluster_id is None:
            pytest.skip("No clusters available")

        resp = client.post("/api/maintenance", json={
            "cluster_id": cluster_id,
            "start_time": "2026-03-08T06:00:00",
            "end_time": "2026-03-08T00:00:00",
        })
        assert resp.status_code == 422

    def test_create_cluster_not_found(self, client):
        resp = client.post("/api/maintenance", json={
            "cluster_id": 9999,
            "start_time": "2026-03-08T00:00:00",
            "end_time": "2026-03-08T06:00:00",
        })
        assert resp.status_code == 404

    def test_delete_maintenance_window(self, client):
        cluster_id = self._create_cluster(client)
        if cluster_id is None:
            pytest.skip("No clusters available")

        r = client.post("/api/maintenance", json={
            "cluster_id": cluster_id,
            "start_time": "2026-03-10T00:00:00",
            "end_time": "2026-03-10T06:00:00",
        })
        window_id = r.json()["id"]

        resp = client.delete(f"/api/maintenance/{window_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = client.get("/api/maintenance")
        ids = [w["id"] for w in resp.json()["windows"]]
        assert window_id not in ids

    def test_delete_not_found(self, client):
        resp = client.delete("/api/maintenance/9999")
        assert resp.status_code == 404
