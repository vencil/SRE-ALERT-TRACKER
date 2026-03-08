"""Tests for weekly tasks and report task assignment API endpoints."""

import pytest


class TestWeeklyTasksCRUD:
    def test_list_tasks_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_create_task(self, client):
        resp = client.post("/api/tasks", json={"title": "Check Grafana dashboards"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Check Grafana dashboards"
        assert data["is_active"] is True

    def test_update_task(self, client):
        r = client.post("/api/tasks", json={"title": "Old title"})
        task_id = r.json()["id"]

        resp = client.patch(f"/api/tasks/{task_id}", json={"title": "New title"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New title"

    def test_deactivate_task(self, client):
        r = client.post("/api/tasks", json={"title": "Temp task"})
        task_id = r.json()["id"]

        resp = client.patch(f"/api/tasks/{task_id}", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Should not appear in default list
        resp = client.get("/api/tasks")
        assert all(t["id"] != task_id for t in resp.json()["tasks"])

    def test_update_task_not_found(self, client):
        resp = client.patch("/api/tasks/9999", json={"title": "x"})
        assert resp.status_code == 404


class TestReportTaskAssignments:
    def test_list_report_tasks(self, client):
        # Create task + report
        client.post("/api/tasks", json={"title": "Task A"})
        r = client.post("/api/reports", json={"year": 2026, "week_number": 10})
        report_id = r.json()["id"]

        resp = client.get(f"/api/reports/{report_id}/tasks")
        assert resp.status_code == 200
        assignments = resp.json()["assignments"]
        assert len(assignments) >= 1
        assert assignments[0]["is_checked"] is False

    def test_toggle_task(self, client):
        client.post("/api/tasks", json={"title": "Task B"})
        r = client.post("/api/reports", json={"year": 2026, "week_number": 11})
        report_id = r.json()["id"]

        # Get task ID
        tasks = client.get(f"/api/reports/{report_id}/tasks").json()["assignments"]
        task_id = tasks[0]["task_id"]

        # Check the task
        resp = client.patch(
            f"/api/reports/{report_id}/tasks/{task_id}",
            json={"is_checked": True, "checked_by": "dev-user"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_checked"] is True
        assert resp.json()["checked_by"] == "dev-user"

    def test_report_not_found(self, client):
        resp = client.get("/api/reports/9999/tasks")
        assert resp.status_code == 404
