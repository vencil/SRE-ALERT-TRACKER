"""Tests for dedup logic — fingerprint computation and upsert behavior."""

from datetime import date, datetime

from models.cluster import Cluster
from models.daily_section import DailySection
from models.shift_report import ShiftReport
from services.dedup import compute_fingerprint, upsert_alert


def _seed_section(db_session):
    """Create cluster + report + section for testing."""
    cluster = Cluster(
        name="test-cluster",
        prometheus_url="http://prom:9090",
        alertmanager_url="http://am:9093",
    )
    db_session.add(cluster)
    db_session.flush()

    report = ShiftReport(year=2026, week_number=11)
    db_session.add(report)
    db_session.flush()

    section = DailySection(report_id=report.id, section_date=date(2026, 3, 9))
    db_session.add(section)
    db_session.flush()

    return cluster, report, section


class TestComputeFingerprint:
    def test_deterministic(self):
        labels = {"alertname": "HighCPU", "severity": "critical", "instance": "pod-1"}
        fp1 = compute_fingerprint(labels)
        fp2 = compute_fingerprint(labels)
        assert fp1 == fp2

    def test_order_independent(self):
        fp1 = compute_fingerprint({"a": "1", "b": "2", "c": "3"})
        fp2 = compute_fingerprint({"c": "3", "a": "1", "b": "2"})
        assert fp1 == fp2

    def test_different_labels_different_fp(self):
        fp1 = compute_fingerprint({"alertname": "A"})
        fp2 = compute_fingerprint({"alertname": "B"})
        assert fp1 != fp2

    def test_returns_16_char_hex(self):
        fp = compute_fingerprint({"alertname": "Test"})
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)


class TestUpsertAlert:
    def test_insert_new_alert(self, db_session):
        cluster, report, section = _seed_section(db_session)

        result = upsert_alert(
            db=db_session,
            daily_section=section,
            cluster_id=cluster.id,
            fingerprint="abc123",
            alert_name="TestAlert",
            severity="warning",
            instance="pod-1",
            source_group="job-a",
            runbook_url="https://example.com/runbook",
            firing_at=datetime(2026, 3, 9, 10, 0),
        )
        db_session.flush()

        assert result.id is not None
        assert result.occurrence_count == 1
        assert result.alert_name == "TestAlert"
        assert result.first_firing_at == datetime(2026, 3, 9, 10, 0)

    def test_dedup_increments_count(self, db_session):
        cluster, report, section = _seed_section(db_session)

        # First insert
        upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="abc123", alert_name="TestAlert", severity="warning",
            instance="pod-1", source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 10, 0),
        )
        db_session.flush()

        # Second upsert — same fingerprint, same report
        result = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="abc123", alert_name="TestAlert", severity="warning",
            instance="pod-1", source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 14, 0),
        )
        db_session.flush()

        assert result.occurrence_count == 2
        assert result.last_firing_at == datetime(2026, 3, 9, 14, 0)

    def test_different_fingerprint_creates_new(self, db_session):
        cluster, report, section = _seed_section(db_session)

        upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp-1", alert_name="Alert-A", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 10, 0),
        )
        upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp-2", alert_name="Alert-B", severity="critical",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 10, 0),
        )
        db_session.flush()

        from models.alert_record import AlertRecord
        count = db_session.query(AlertRecord).count()
        assert count == 2

    def test_auto_resolved_flag(self, db_session):
        cluster, report, section = _seed_section(db_session)

        result = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp-resolved", alert_name="ResolvedAlert", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 10, 0), auto_resolved=True,
        )
        db_session.flush()
        assert result.auto_resolved is True

    def test_last_firing_at_takes_max(self, db_session):
        cluster, report, section = _seed_section(db_session)

        # Insert with later time first
        upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp-time", alert_name="TimeTest", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 15, 0),
        )
        db_session.flush()

        # Upsert with earlier time — should NOT overwrite
        result = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp-time", alert_name="TimeTest", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 10, 0),
        )
        db_session.flush()

        assert result.last_firing_at == datetime(2026, 3, 9, 15, 0)
