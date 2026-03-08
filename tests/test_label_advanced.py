"""Tests for label merge and soft-delete endpoints."""

import pytest


class TestLabelSoftDelete:
    def test_soft_delete(self, client):
        r = client.post("/api/labels", json={"name": "to-delete"})
        label_id = r.json()["id"]

        resp = client.delete(f"/api/labels/{label_id}")
        assert resp.status_code == 204

        # Should not appear in default list
        resp = client.get("/api/labels")
        assert all(l["id"] != label_id for l in resp.json()["labels"])

        # Should appear when including inactive
        resp = client.get("/api/labels", params={"include_inactive": True})
        found = [l for l in resp.json()["labels"] if l["id"] == label_id]
        assert len(found) == 1
        assert found[0]["is_active"] is False

    def test_soft_delete_not_found(self, client):
        resp = client.delete("/api/labels/9999")
        assert resp.status_code == 404


class TestLabelMerge:
    def test_merge_labels(self, client):
        r1 = client.post("/api/labels", json={"name": "source-label"})
        r2 = client.post("/api/labels", json={"name": "target-label"})
        source_id = r1.json()["id"]
        target_id = r2.json()["id"]

        resp = client.post("/api/labels/merge", json={
            "source_id": source_id,
            "target_id": target_id,
        })
        assert resp.status_code == 200
        assert resp.json()["id"] == target_id

        # Source should be deactivated
        resp = client.get("/api/labels", params={"include_inactive": True})
        source = [l for l in resp.json()["labels"] if l["id"] == source_id]
        assert source[0]["is_active"] is False

    def test_merge_same_label(self, client):
        r = client.post("/api/labels", json={"name": "self-merge"})
        label_id = r.json()["id"]

        resp = client.post("/api/labels/merge", json={
            "source_id": label_id,
            "target_id": label_id,
        })
        assert resp.status_code == 422

    def test_merge_source_not_found(self, client):
        r = client.post("/api/labels", json={"name": "target-only"})
        resp = client.post("/api/labels/merge", json={
            "source_id": 9999,
            "target_id": r.json()["id"],
        })
        assert resp.status_code == 404

    def test_merge_target_not_found(self, client):
        r = client.post("/api/labels", json={"name": "source-only"})
        resp = client.post("/api/labels/merge", json={
            "source_id": r.json()["id"],
            "target_id": 9999,
        })
        assert resp.status_code == 404
