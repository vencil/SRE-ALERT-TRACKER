"""Tests for Labels API (CRUD)."""


class TestLabelsCRUD:
    def test_list_labels_empty(self, client):
        resp = client.get("/api/labels")
        assert resp.status_code == 200
        assert resp.json()["labels"] == []

    def test_create_label(self, client):
        resp = client.post("/api/labels", json={
            "name": "database",
            "color": "#ef4444",
            "description": "Database related alerts",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "database"
        assert data["color"] == "#ef4444"
        assert data["is_active"] is True

    def test_create_duplicate_label_fails(self, client):
        client.post("/api/labels", json={"name": "database"})
        resp = client.post("/api/labels", json={"name": "database"})
        assert resp.status_code == 409

    def test_update_label(self, client):
        create_resp = client.post("/api/labels", json={"name": "database"})
        label_id = create_resp.json()["id"]

        resp = client.patch(f"/api/labels/{label_id}", json={
            "color": "#3b82f6",
            "description": "Updated description",
        })
        assert resp.status_code == 200
        assert resp.json()["color"] == "#3b82f6"

    def test_update_label_not_found(self, client):
        resp = client.patch("/api/labels/999", json={"name": "x"})
        assert resp.status_code == 404

    def test_deactivate_label(self, client):
        create_resp = client.post("/api/labels", json={"name": "temp"})
        label_id = create_resp.json()["id"]

        client.patch(f"/api/labels/{label_id}", json={"is_active": False})

        # Should not appear in default listing
        resp = client.get("/api/labels")
        assert len(resp.json()["labels"]) == 0

        # Should appear with include_inactive
        resp = client.get("/api/labels?include_inactive=true")
        assert len(resp.json()["labels"]) == 1

    def test_rename_label_uniqueness(self, client):
        client.post("/api/labels", json={"name": "alpha"})
        create_resp = client.post("/api/labels", json={"name": "beta"})
        beta_id = create_resp.json()["id"]

        resp = client.patch(f"/api/labels/{beta_id}", json={"name": "alpha"})
        assert resp.status_code == 409
