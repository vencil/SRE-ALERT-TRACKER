"""Filter engine — whitelist/blacklist evaluation for incoming alerts."""

import fnmatch
import logging
from sqlalchemy.orm import Session

from models.filter_rule import AlertFilterRule

logger = logging.getLogger("alert-tracker.filter")


def load_active_rules(db: Session) -> list[AlertFilterRule]:
    """Load all active filter rules from DB."""
    return (
        db.query(AlertFilterRule)
        .filter(AlertFilterRule.is_active.is_(True))
        .all()
    )


def apply_filters(alerts: list[dict], rules: list[AlertFilterRule]) -> list[dict]:
    """Apply whitelist/blacklist rules to a list of raw alert dicts.

    Each alert dict is expected to have keys: 'alertname', 'group', 'severity'.

    Evaluation order:
    1. If ANY whitelist rules exist → only keep alerts matching whitelist
    2. Then apply blacklist rules → exclude matching alerts
    3. No rules → keep all

    filter_value supports fnmatch-style wildcards (e.g. "MariaDB*").
    """
    if not rules:
        return alerts

    whitelist_rules = [r for r in rules if r.rule_type == "whitelist"]
    blacklist_rules = [r for r in rules if r.rule_type == "blacklist"]

    # Step 1: Whitelist filtering
    if whitelist_rules:
        filtered = []
        for alert in alerts:
            if _matches_any(alert, whitelist_rules):
                filtered.append(alert)
        logger.debug(
            "Whitelist: %d/%d alerts passed", len(filtered), len(alerts),
        )
    else:
        filtered = list(alerts)

    # Step 2: Blacklist filtering
    if blacklist_rules:
        before = len(filtered)
        filtered = [a for a in filtered if not _matches_any(a, blacklist_rules)]
        logger.debug(
            "Blacklist: removed %d alerts, %d remaining",
            before - len(filtered), len(filtered),
        )

    return filtered


def _matches_any(alert: dict, rules: list[AlertFilterRule]) -> bool:
    """Check if an alert matches any of the given rules.

    Missing or None field values are treated as empty strings for fnmatch.
    This allows wildcard patterns like '*' to match alerts with empty fields.
    """
    for rule in rules:
        field_value = alert.get(rule.filter_field, "")
        if field_value is None:
            field_value = ""  # Normalize None → "" for fnmatch compatibility
        if fnmatch.fnmatch(field_value, rule.filter_value):
            return True
    return False
