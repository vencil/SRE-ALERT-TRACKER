"""E2E critical workflow — navigate report → view alerts → debounce auto-save.

Requires: running app (`make dev`) + seeded test data (via conftest).
Run with: make test-e2e
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestReportNavigation:
    """Test: landing page → click report link → report detail page."""

    def test_report_list_shows_current_week(
        self, page: Page, base_url: str, seeded_report: dict
    ):
        """Report list page shows a link for the seeded week."""
        page.goto(base_url)
        year = seeded_report["year"]
        week = seeded_report["week_number"]

        # Report link format: "{year} 年第 {week_number} 週"
        link = page.get_by_role("link", name=f"{year} 年第 {week} 週")
        expect(link).to_be_visible(timeout=10000)

    def test_navigate_to_report_detail(
        self, page: Page, base_url: str, seeded_report: dict
    ):
        """Click report link → navigates to report detail page."""
        page.goto(base_url)
        year = seeded_report["year"]
        week = seeded_report["week_number"]

        link = page.get_by_role("link", name=f"{year} 年第 {week} 週")
        link.click()

        page.wait_for_url(f"**/reports/{seeded_report['report_id']}", timeout=10000)


@pytest.mark.e2e
class TestAlertCardVisibility:
    """Test: alert cards are visible with correct structure."""

    def test_alert_cards_rendered(self, report_page: Page, seeded_report: dict):
        """Report detail page shows alert cards for seeded alerts."""
        cards = report_page.locator(".alert-card")
        expect(cards.first).to_be_visible()
        # We seeded 3 alerts
        assert cards.count() >= seeded_report["alert_count"]

    def test_alert_card_has_phenomenon_textarea(self, report_page: Page):
        """Each alert card has a '填寫現象...' placeholder textarea."""
        textarea = report_page.get_by_placeholder("填寫現象...")
        expect(textarea.first).to_be_visible()

    def test_alert_card_has_impact_textarea(self, report_page: Page):
        """Each alert card has a '填寫影響...' placeholder textarea."""
        textarea = report_page.get_by_placeholder("填寫影響...")
        expect(textarea.first).to_be_visible()

    def test_alert_card_has_action_textarea(self, report_page: Page):
        """Each alert card has a '填寫處理作法...' placeholder textarea."""
        textarea = report_page.get_by_placeholder("填寫處理作法...")
        expect(textarea.first).to_be_visible()


@pytest.mark.e2e
class TestDebounceAutoSave:
    """Test: fill textarea → debounce triggers save → reload persists."""

    @pytest.mark.parametrize("placeholder, test_text", [
        ("填寫現象...", "E2E test: high CPU on node-3"),
        ("填寫影響...", "E2E test: service degradation"),
        ("填寫處理作法...", "E2E test: scaled up pods"),
    ])
    def test_textarea_auto_save(self, report_page: Page, placeholder: str, test_text: str):
        """Type in textarea → 'saved' indicator → reload persists."""
        textarea = report_page.get_by_placeholder(placeholder).first

        textarea.fill(test_text)

        # Wait for debounce (800ms) + API round-trip → "saved" indicator
        saved = report_page.locator(".save-indicator").first
        expect(saved).to_have_text("saved", timeout=5000)

        # Reload and verify persistence
        report_page.reload()
        report_page.locator(".alert-card").first.wait_for(
            state="visible", timeout=10000
        )
        textarea_after = report_page.get_by_placeholder(placeholder).first
        expect(textarea_after).to_have_value(test_text)
