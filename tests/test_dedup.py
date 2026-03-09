"""Tests for dedup logic — fingerprint computation and upsert behavior."""

from datetime import date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from models.alert_record import AlertRecord
from services.dedup import compute_fingerprint, upsert_alert


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
    def test_insert_new_alert(self, db_session, seed_report_section):
        cluster, report, section = seed_report_section

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

    def test_dedup_increments_count(self, db_session, seed_report_section):
        cluster, report, section = seed_report_section

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

    def test_different_fingerprint_creates_new(self, db_session, seed_report_section):
        cluster, report, section = seed_report_section

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

    def test_auto_resolved_flag(self, db_session, seed_report_section):
        cluster, report, section = seed_report_section

        result = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp-resolved", alert_name="ResolvedAlert", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 10, 0), auto_resolved=True,
        )
        db_session.flush()
        assert result.auto_resolved is True

    def test_last_firing_at_takes_max(self, db_session, seed_report_section):
        cluster, report, section = seed_report_section

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

    def test_unique_constraint_prevents_duplicate_insert(self, db_session, seed_report_section):
        """Verify DB-level UniqueConstraint(daily_section_id, fingerprint) blocks duplicates.

        This tests the defensive guard added in case the ORM-level dedup
        (with_for_update) is bypassed by a race condition.
        """
        cluster, report, section = seed_report_section

        # Insert first record via ORM directly (bypass dedup logic)
        alert1 = AlertRecord(
            daily_section_id=section.id,
            cluster_id=cluster.id,
            fingerprint="dup-fp",
            alert_name="DupAlert",
            severity="warning",
            occurrence_count=1,
        )
        db_session.add(alert1)
        db_session.commit()

        # Attempt to insert duplicate — same section + fingerprint
        alert2 = AlertRecord(
            daily_section_id=section.id,
            cluster_id=cluster.id,
            fingerprint="dup-fp",
            alert_name="DupAlert",
            severity="warning",
            occurrence_count=1,
        )
        db_session.add(alert2)
        with pytest.raises(IntegrityError):
            db_session.commit()

        # Cleanup: rollback so session is usable
        db_session.rollback()

    def test_different_section_same_fingerprint_allowed(self, db_session, seed_report_section):
        """Same fingerprint in different daily sections should be allowed."""
        cluster, report, section = seed_report_section

        # Create a second section (different date)
        from models.daily_section import DailySection
        section2 = DailySection(report_id=report.id, section_date=date(2026, 3, 10))
        db_session.add(section2)
        db_session.flush()

        # Insert same fingerprint into both sections — should succeed
        for sec in [section, section2]:
            alert = AlertRecord(
                daily_section_id=sec.id,
                cluster_id=cluster.id,
                fingerprint="cross-section-fp",
                alert_name="CrossSectionAlert",
                severity="warning",
                occurrence_count=1,
            )
            db_session.add(alert)

        db_session.commit()  # Should NOT raise
        count = db_session.query(AlertRecord).filter_by(fingerprint="cross-section-fp").count()
        assert count == 2
