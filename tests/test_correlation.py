"""Tests for Dashboard Correlation API (GET /api/dashboard/correlation)."""

from datetime import date, datetime

from models.alert_record import AlertRecord
from models.cluster import Cluster
from models.daily_section import DailySection
from models.shift_report import ShiftReport


def _seed_overlapping_alerts(db_session):
    """Create alerts with overlapping time intervals for correlation testing."""
    cluster = Cluster(name="prod", prometheus_url="", alertmanager_url="")
    db_session.add(cluster)
    db_session.flush()

    report = ShiftReport(year=2026, week_number=11)
    db_session.add(report)
    db_session.flush()

    section = DailySection(report_id=report.id, section_date=date(2026, 3, 9))
    db_session.add(section)
    db_session.flush()

    # Alert A: 08:00 ~ 08:30
    a = AlertRecord(
        daily_section_id=section.id, cluster_id=cluster.id,
        fingerprint="fp_a", alert_name="HighCPU", severity="critical",
        instance="pod-1", occurrence_count=3,
        first_firing_at=datetime(2026, 3, 9, 8, 0),
        last_firing_at=datetime(2026, 3, 9, 8, 30),
    )
    # Alert B: 08:15 ~ 09:00 (overlaps A)
    b = AlertRecord(
        daily_section_id=section.id, cluster_id=cluster.id,
        fingerprint="fp_b", alert_name="HighMemory", severity="warning",
        instance="pod-1", occurrence_count=2,
        first_firing_at=datetime(2026, 3, 9, 8, 15),
        last_firing_at=datetime(2026, 3, 9, 9, 0),
    )
    # Alert C: 14:00 ~ 14:30 (isolated, no overlap)
    c = AlertRecord(
        daily_section_id=section.id, cluster_id=cluster.id,
        fingerprint="fp_c", alert_name="DiskFull", severity="critical",
        instance="node-2", occurrence_count=1,
        first_firing_at=datetime(2026, 3, 9, 14, 0),
        last_firing_at=datetime(2026, 3, 9, 14, 30),
    )
    db_session.add_all([a, b, c])
    db_session.commit()
    return cluster, report


class TestCorrelation:
    def test_correlation_empty_week(self, client):
        """Non-existent week returns empty groups."""
        resp = client.get("/api/dashboard/correlation", params={"year": 2099, "week": 1})
        assert resp.status_code == 200
        assert resp.json()["groups"] == []

    def test_correlation_overlapping_group(self, client, db_session):
        """Overlapping alerts A and B should form a single group."""
        cluster, _ = _seed_overlapping_alerts(db_session)
        resp = client.get("/api/dashboard/correlation", params={"year": 2026, "week": 11})
        assert resp.status_code == 200
        data = resp.json()

        assert data["year"] == 2026
        assert data["week"] == 11
        assert len(data["groups"]) == 1  # Only one overlapping group

        group = data["groups"][0]
        assert group["alert_count"] == 2
        alert_names = {a["alert_name"] for a in group["alerts"]}
        assert alert_names == {"HighCPU", "HighMemory"}

    def test_correlation_isolated_alert_excluded(self, client, db_session):
        """Isolated alert C should not form a group (needs 2+ alerts)."""
        _seed_overlapping_alerts(db_session)
        resp = client.get("/api/dashboard/correlation", params={"year": 2026, "week": 11})
        data = resp.json()

        # Only 1 group, and it shouldn't contain DiskFull
        all_alert_names = set()
        for g in data["groups"]:
            for a in g["alerts"]:
                all_alert_names.add(a["alert_name"])
        assert "DiskFull" not in all_alert_names

    def test_correlation_window_boundaries(self, client, db_session):
        """Group window_start/end should span the full overlap range."""
        _seed_overlapping_alerts(db_session)
        resp = client.get("/api/dashboard/correlation", params={"year": 2026, "week": 11})
        group = resp.json()["groups"][0]

        # A starts at 08:00, B ends at 09:00
        assert "08:00" in group["window_start"]
        assert "09:00" in group["window_end"]

    def test_correlation_cluster_filter(self, client, db_session):
        """Filtering by non-existent cluster should return empty groups."""
        _seed_overlapping_alerts(db_session)
        resp = client.get("/api/dashboard/correlation", params={
            "year": 2026, "week": 11, "cluster_id": 99999,
        })
        assert resp.status_code == 200
        assert resp.json()["groups"] == []

    def test_correlation_three_way_overlap(self, client, db_session):
        """Three alerts all overlapping should form a single group of 3."""
        cluster = Cluster(name="c1", prometheus_url="", alertmanager_url="")
        db_session.add(cluster)
        db_session.flush()

        report = ShiftReport(year=2026, week_number=12)
        db_session.add(report)
        db_session.flush()
        section = DailySection(report_id=report.id, section_date=date(2026, 3, 16))
        db_session.add(section)
        db_session.flush()

        # All three overlap: A=[10:00, 10:30], B=[10:10, 10:40], C=[10:20, 10:50]
        for i, (start_m, end_m, name) in enumerate([
            (0, 30, "AlertX"), (10, 40, "AlertY"), (20, 50, "AlertZ"),
        ]):
            db_session.add(AlertRecord(
                daily_section_id=section.id, cluster_id=cluster.id,
                fingerprint=f"fp_{i}", alert_name=name, severity="warning",
                occurrence_count=1,
                first_firing_at=datetime(2026, 3, 16, 10, start_m),
                last_firing_at=datetime(2026, 3, 16, 10, end_m),
            ))
        db_session.commit()

        resp = client.get("/api/dashboard/correlation", params={"year": 2026, "week": 12})
        data = resp.json()
        assert len(data["groups"]) == 1
        assert data["groups"][0]["alert_count"] == 3

    def test_correlation_no_firing_times_excluded(self, client, db_session):
        """Alerts without first_firing_at should be excluded from correlation."""
        cluster = Cluster(name="c1", prometheus_url="", alertmanager_url="")
        db_session.add(cluster)
        db_session.flush()
        report = ShiftReport(year=2026, week_number=13)
        db_session.add(report)
        db_session.flush()
        section = DailySection(report_id=report.id, section_date=date(2026, 3, 23))
        db_session.add(section)
        db_session.flush()

        # Alert without firing timestamps
        db_session.add(AlertRecord(
            daily_section_id=section.id, cluster_id=cluster.id,
            fingerprint="fp_nots", alert_name="NoTimestamp", severity="info",
            occurrence_count=1,
        ))
        db_session.commit()

        resp = client.get("/api/dashboard/correlation", params={"year": 2026, "week": 13})
        assert resp.status_code == 200
        assert resp.json()["groups"] == []
