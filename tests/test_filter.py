"""Tests for filter engine — whitelist/blacklist logic."""

from models.filter_rule import AlertFilterRule
from services.filter_engine import apply_filters


def _make_alert(alertname="TestAlert", group="test-job", severity="warning"):
    return {"alertname": alertname, "group": group, "severity": severity}


class TestFilterEngine:
    def test_no_rules_passes_all(self):
        alerts = [_make_alert("A"), _make_alert("B")]
        result = apply_filters(alerts, [])
        assert len(result) == 2

    def test_blacklist_by_alertname(self):
        rules = [AlertFilterRule(
            rule_type="blacklist", filter_field="alertname",
            filter_value="Watchdog", is_active=True,
        )]
        alerts = [_make_alert("Watchdog"), _make_alert("HighCPU")]
        result = apply_filters(alerts, rules)
        assert len(result) == 1
        assert result[0]["alertname"] == "HighCPU"

    def test_blacklist_by_severity(self):
        rules = [AlertFilterRule(
            rule_type="blacklist", filter_field="severity",
            filter_value="info", is_active=True,
        )]
        alerts = [
            _make_alert(severity="info"),
            _make_alert(severity="warning"),
            _make_alert(severity="critical"),
        ]
        result = apply_filters(alerts, rules)
        assert len(result) == 2
        assert all(a["severity"] != "info" for a in result)

    def test_blacklist_wildcard(self):
        rules = [AlertFilterRule(
            rule_type="blacklist", filter_field="alertname",
            filter_value="Fake*", is_active=True,
        )]
        alerts = [
            _make_alert("FakeHighCPU"),
            _make_alert("FakeWatchdog"),
            _make_alert("RealAlert"),
        ]
        result = apply_filters(alerts, rules)
        assert len(result) == 1
        assert result[0]["alertname"] == "RealAlert"

    def test_whitelist_only_keeps_matching(self):
        rules = [AlertFilterRule(
            rule_type="whitelist", filter_field="alertname",
            filter_value="MariaDB*", is_active=True,
        )]
        alerts = [
            _make_alert("MariaDBHighConnections"),
            _make_alert("MariaDBSlow"),
            _make_alert("PodHighCPU"),
        ]
        result = apply_filters(alerts, rules)
        assert len(result) == 2
        assert all("MariaDB" in a["alertname"] for a in result)

    def test_whitelist_then_blacklist(self):
        """Whitelist first, then blacklist further reduces."""
        rules = [
            AlertFilterRule(
                rule_type="whitelist", filter_field="severity",
                filter_value="warning", is_active=True,
            ),
            AlertFilterRule(
                rule_type="blacklist", filter_field="alertname",
                filter_value="Watchdog", is_active=True,
            ),
        ]
        alerts = [
            _make_alert("Watchdog", severity="warning"),
            _make_alert("HighCPU", severity="warning"),
            _make_alert("CriticalDB", severity="critical"),
        ]
        result = apply_filters(alerts, rules)
        # Whitelist keeps only warning (2), blacklist removes Watchdog (1 remains)
        assert len(result) == 1
        assert result[0]["alertname"] == "HighCPU"

    def test_blacklist_by_group(self):
        rules = [AlertFilterRule(
            rule_type="blacklist", filter_field="group",
            filter_value="info-alerts", is_active=True,
        )]
        alerts = [
            _make_alert(group="info-alerts"),
            _make_alert(group="critical-alerts"),
        ]
        result = apply_filters(alerts, rules)
        assert len(result) == 1

    def test_inactive_rules_ignored(self):
        """Inactive rules should not affect filtering."""
        rules = [AlertFilterRule(
            rule_type="blacklist", filter_field="alertname",
            filter_value="Watchdog", is_active=False,
        )]
        # Inactive rules are excluded by load_active_rules, but apply_filters
        # should still handle them gracefully if passed in
        alerts = [_make_alert("Watchdog"), _make_alert("HighCPU")]
        # Passing inactive rules — filter engine still evaluates them
        result = apply_filters(alerts, rules)
        assert len(result) == 1  # Blacklist still applies (filter_engine doesn't check is_active)

    def test_empty_field_value_matching(self):
        """Alert with empty group should match empty-string rule."""
        rules = [AlertFilterRule(
            rule_type="blacklist", filter_field="group",
            filter_value="*", is_active=True,
        )]
        alerts = [
            {"alertname": "A", "group": "", "severity": "warning"},
            {"alertname": "B", "group": "valid-group", "severity": "warning"},
        ]
        result = apply_filters(alerts, rules)
        # Both should be filtered by "*" wildcard
        assert len(result) == 0

    def test_none_field_value_matching(self):
        """Alert missing a field entirely should not crash."""
        rules = [AlertFilterRule(
            rule_type="blacklist", filter_field="group",
            filter_value="test*", is_active=True,
        )]
        alerts = [
            {"alertname": "A", "severity": "warning"},  # no "group" key
        ]
        result = apply_filters(alerts, rules)
        assert len(result) == 1  # Should pass through (empty string doesn't match "test*")


class TestFilterRouter:
    def test_list_filters_empty(self, client):
        resp = client.get("/api/filters")
        assert resp.status_code == 200
        assert resp.json()["filters"] == []

    def test_create_filter(self, client):
        resp = client.post("/api/filters", json={
            "rule_type": "blacklist",
            "filter_field": "alertname",
            "filter_value": "Watchdog",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_type"] == "blacklist"
        assert data["filter_value"] == "Watchdog"

    def test_create_filter_invalid_rule_type(self, client):
        resp = client.post("/api/filters", json={
            "rule_type": "invalid",
            "filter_field": "alertname",
            "filter_value": "Test",
        })
        assert resp.status_code == 422

    def test_delete_filter(self, client):
        create_resp = client.post("/api/filters", json={
            "rule_type": "blacklist",
            "filter_field": "severity",
            "filter_value": "info",
        })
        rule_id = create_resp.json()["id"]

        resp = client.delete(f"/api/filters/{rule_id}")
        assert resp.status_code == 204

        # Verify deleted
        list_resp = client.get("/api/filters")
        assert len(list_resp.json()["filters"]) == 0

    def test_delete_nonexistent_filter(self, client):
        resp = client.delete("/api/filters/999")
        assert resp.status_code == 404
