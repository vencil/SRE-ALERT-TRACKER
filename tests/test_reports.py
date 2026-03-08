"""Tests for Reports API (CRUD + daily sections)."""


class TestReportsCRUD:
    def test_list_reports_empty(self, client):
        resp = client.get("/api/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["reports"] == []

    def test_create_report(self, client):
        resp = client.post("/api/reports", json={
            "year": 2026,
            "week_number": 11,
            "operator_name": "poyu",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["year"] == 2026
        assert data["week_number"] == 11
        assert data["operator_name"] == "poyu"
        # Should have 7 daily sections (Mon-Sun)
        assert len(data["daily_sections"]) == 7

    def test_create_duplicate_report_fails(self, client):
        client.post("/api/reports", json={"year": 2026, "week_number": 11})
        resp = client.post("/api/reports", json={"year": 2026, "week_number": 11})
        assert resp.status_code == 409

    def test_get_report(self, client):
        create_resp = client.post("/api/reports", json={"year": 2026, "week_number": 10})
        report_id = create_resp.json()["id"]

        resp = client.get(f"/api/reports/{report_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == report_id

    def test_get_report_not_found(self, client):
        resp = client.get("/api/reports/999")
        assert resp.status_code == 404

    def test_update_report(self, client):
        create_resp = client.post("/api/reports", json={"year": 2026, "week_number": 10})
        report_id = create_resp.json()["id"]

        resp = client.patch(f"/api/reports/{report_id}", json={
            "operator_name": "john",
            "notes": "Quiet week",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["operator_name"] == "john"
        assert data["notes"] == "Quiet week"

    def test_list_reports_with_filter(self, client):
        client.post("/api/reports", json={"year": 2026, "week_number": 10})
        client.post("/api/reports", json={"year": 2026, "week_number": 11})
        client.post("/api/reports", json={"year": 2025, "week_number": 50})

        resp = client.get("/api/reports?year=2026")
        assert resp.json()["total"] == 2

        resp = client.get("/api/reports?year=2026&week=11")
        assert resp.json()["total"] == 1

    def test_list_reports_pagination(self, client):
        for w in range(1, 6):
            client.post("/api/reports", json={"year": 2026, "week_number": w})

        resp = client.get("/api/reports?offset=0&limit=2")
        data = resp.json()
        assert data["total"] == 5
        assert len(data["reports"]) == 2


class TestReportEdgeCases:
    def test_create_report_invalid_week_53(self, client):
        """Week 53 is only valid for certain years."""
        # 2021 does not have week 53 (ISO 8601)
        resp = client.post("/api/reports", json={"year": 2021, "week_number": 53})
        assert resp.status_code == 422

    def test_create_report_valid_week_53(self, client):
        """2020 has 53 ISO weeks — should succeed."""
        resp = client.post("/api/reports", json={"year": 2020, "week_number": 53})
        assert resp.status_code == 201

    def test_create_report_week_1_year_boundary(self, client):
        """Week 1 of 2026 — first section should be Mon Dec 29, 2025."""
        resp = client.post("/api/reports", json={"year": 2026, "week_number": 1})
        assert resp.status_code == 201
        sections = resp.json()["daily_sections"]
        assert sections[0]["section_date"] == "2025-12-29"
        assert sections[6]["section_date"] == "2026-01-04"


class TestDailySections:
    def test_update_section(self, client):
        create_resp = client.post("/api/reports", json={"year": 2026, "week_number": 10})
        section_id = create_resp.json()["daily_sections"][0]["id"]

        resp = client.patch(f"/api/sections/{section_id}", json={
            "operator_name": "alice",
            "daily_notes": "Swap shift",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["operator_name"] == "alice"
        assert data["daily_notes"] == "Swap shift"
