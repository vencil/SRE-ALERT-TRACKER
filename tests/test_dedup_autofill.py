"""Tests for auto-fill from annotations and raw_labels/raw_annotations storage."""

from datetime import datetime

from services.dedup import upsert_alert


class TestAutoFillFromAnnotations:
    def test_fills_phenomenon_from_summary(self, db_session, seed_report_section):
        cluster, _, section = seed_report_section
        alert = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp1", alert_name="TestAlert", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 8, 0),
            raw_annotations={"summary": "High CPU on pod-01", "description": "Pod is using 95% CPU"},
        )
        assert alert.phenomenon == "High CPU on pod-01"
        assert alert.impact == "Pod is using 95% CPU"

    def test_does_not_overwrite_manual_fields(self, db_session, seed_report_section):
        cluster, _, section = seed_report_section
        alert = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp2", alert_name="TestAlert2", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 8, 0),
            raw_annotations={"summary": "auto-text"},
        )
        # First insert fills phenomenon
        assert alert.phenomenon == "auto-text"

        # Simulate operator editing
        alert.phenomenon = "Manually written"
        alert.manually_edited = True
        db_session.flush()

        # Second upsert (same fingerprint) should NOT overwrite
        alert2 = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp2", alert_name="TestAlert2", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 9, 0),
            raw_annotations={"summary": "different-auto-text"},
        )
        assert alert2.phenomenon == "Manually written"

    def test_no_annotations_leaves_fields_empty(self, db_session, seed_report_section):
        cluster, _, section = seed_report_section
        alert = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp3", alert_name="TestAlert3", severity="info",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 8, 0),
            raw_annotations=None,
        )
        assert alert.phenomenon is None
        assert alert.impact is None


class TestRawLabelsStorage:
    def test_raw_labels_stored_on_insert(self, db_session, seed_report_section):
        cluster, _, section = seed_report_section
        labels = {"alertname": "TestAlert", "severity": "warning", "namespace": "prod"}
        annotations = {"summary": "test", "runbook_url": "http://wiki/test"}

        alert = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp4", alert_name="TestAlert", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 8, 0),
            raw_labels=labels, raw_annotations=annotations,
        )
        db_session.commit()
        db_session.refresh(alert)

        assert alert.raw_labels == labels
        assert alert.raw_annotations == annotations
        assert alert.raw_labels["namespace"] == "prod"

    def test_raw_data_updated_on_dedup(self, db_session, seed_report_section):
        cluster, _, section = seed_report_section
        # Insert
        upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp5", alert_name="TestAlert5", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 8, 0),
            raw_labels={"old": "data"},
        )
        db_session.flush()  # Ensure first record is visible to the dedup query
        # Update (same fingerprint) with new raw_labels
        alert = upsert_alert(
            db=db_session, daily_section=section, cluster_id=cluster.id,
            fingerprint="fp5", alert_name="TestAlert5", severity="warning",
            instance=None, source_group=None, runbook_url=None,
            firing_at=datetime(2026, 3, 9, 9, 0),
            raw_labels={"new": "data", "extra": "field"},
        )
        assert alert.raw_labels == {"new": "data", "extra": "field"}
        assert alert.occurrence_count == 2
