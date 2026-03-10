"""Tests for cascade delete behavior — ShiftReport → DailySection → AlertRecord."""

from datetime import date

from models.alert_record import AlertRecord
from models.daily_section import DailySection
from models.shift_report import ShiftReport


class TestCascadeDelete:
    def test_delete_report_cascades_to_sections_and_alerts(self, db_session, seed_report_section):
        """Deleting a ShiftReport should cascade-delete DailySections and AlertRecords."""
        cluster, report, section = seed_report_section

        # Add an alert to the section
        alert = AlertRecord(
            daily_section_id=section.id,
            cluster_id=cluster.id,
            fingerprint="cascade-test-fp",
            alert_name="CascadeTest",
            severity="warning",
            occurrence_count=1,
        )
        db_session.add(alert)
        db_session.flush()

        report_id = report.id
        section_id = section.id
        alert_id = alert.id

        # Verify all exist
        assert db_session.get(ShiftReport, report_id) is not None
        assert db_session.get(DailySection, section_id) is not None
        assert db_session.get(AlertRecord, alert_id) is not None

        # Delete the report
        db_session.delete(report)
        db_session.flush()

        # Verify cascade: section and alert should be gone
        assert db_session.get(DailySection, section_id) is None
        assert db_session.get(AlertRecord, alert_id) is None

    def test_delete_section_cascades_to_alerts(self, db_session, seed_report_section):
        """Deleting a DailySection should cascade-delete its AlertRecords."""
        cluster, report, section = seed_report_section

        alert = AlertRecord(
            daily_section_id=section.id,
            cluster_id=cluster.id,
            fingerprint="cascade-section-fp",
            alert_name="CascadeSectionTest",
            severity="critical",
            occurrence_count=1,
        )
        db_session.add(alert)
        db_session.flush()

        alert_id = alert.id

        # Remove section from report's collection (triggers delete-orphan)
        report.daily_sections.remove(section)
        db_session.flush()

        assert db_session.get(AlertRecord, alert_id) is None

    def test_delete_report_with_multiple_sections(self, db_session, seed_report_section):
        """Deleting a report with multiple sections and alerts cascades correctly."""
        cluster, report, section = seed_report_section

        # Add a second section
        section2 = DailySection(report_id=report.id, section_date=date(2026, 3, 10))
        db_session.add(section2)
        db_session.flush()

        # Add alerts to both sections
        for sec, fp in [(section, "fp-s1"), (section2, "fp-s2")]:
            db_session.add(AlertRecord(
                daily_section_id=sec.id,
                cluster_id=cluster.id,
                fingerprint=fp,
                alert_name=f"Alert-{fp}",
                severity="warning",
                occurrence_count=1,
            ))
        db_session.flush()

        assert db_session.query(AlertRecord).count() == 2
        assert db_session.query(DailySection).count() == 2

        # Delete report → everything cascades
        db_session.delete(report)
        db_session.flush()

        assert db_session.query(AlertRecord).count() == 0
        assert db_session.query(DailySection).count() == 0
        assert db_session.query(ShiftReport).count() == 0
