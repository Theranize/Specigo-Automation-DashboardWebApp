"""Re-Assignment Log page object."""

from typing import Optional
from playwright.sync_api import Locator
from pages.base_page import BasePage
from locators.accession.reassignment_locators import (
    SIDEBAR_ACCESSION_TEXT,
    SIDEBAR_REASSIGNMENT_LOG_TEXT,
    SEARCH_PLACEHOLDER,
    SEARCH_NAME_NTH,
    SEARCH_MOBILE_NTH,
    SEARCH_BUTTON_NAME,
    TABLE_ROWS_SELECTOR,
    ROW_SAMPLE_NAME_TD,
    ASSIGN_BUTTON_NAME,
    ASSIGN_MODAL_SELECTOR,
    NOTE_INPUT_SELECTOR,
    MODAL_ASSIGN_BUTTON_NAME,
)


class ReassignmentPage(BasePage):
    """Page object for the Re-Assignment Log workflow."""

    def navigate_to_reassignment_log(self) -> None:
        """Navigate to Re-Assignment Log (URL: /reassignmentlog).

        Bypasses the sidebar nav menu — duplicate hidden DOM links break
        strict-mode `.click()` under parallel load. Direct goto is
        deterministic. Wait for the search input to render so subsequent
        `fill_search_filters` doesn't time out on a half-rendered page.
        """
        base = getattr(self.page.context, "base_url", "") or ""
        if "reassignmentlog" not in (self.page.url or ""):
            self.safe_goto(base + "reassignmentlog")
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        try:
            self.page.get_by_placeholder(SEARCH_PLACEHOLDER).first.wait_for(
                state="visible", timeout=20000
            )
        except Exception:
            pass
        self.wait_for_idle(2)

    def fill_search_filters(self, name: str, mobile: str) -> None:
        """Fill name and mobile inputs in the Re-Assignment Log search bar."""
        inputs = self.page.get_by_placeholder(SEARCH_PLACEHOLDER)
        inputs.nth(SEARCH_NAME_NTH).fill(name)
        inputs.nth(SEARCH_MOBILE_NTH).fill(mobile)

    def click_search(self) -> None:
        """Click Search and wait for the table to load."""
        self.page.get_by_role("button", name=SEARCH_BUTTON_NAME).click()
        self.page.wait_for_load_state("networkidle")
        self.wait_for_idle(1.5)

    def wait_for_rows(self) -> bool:
        """Wait for reassignment table rows to appear; returns True if visible."""
        try:
            self.page.locator(TABLE_ROWS_SELECTOR).first.wait_for(
                state="visible", timeout=10000
            )
            return True
        except Exception:
            return False

    def find_row(self, sample_name: str) -> Optional[Locator]:
        """Find row by sample_name (no sample_id used)."""
        rows = self.page.locator(TABLE_ROWS_SELECTOR)
        for i in range(rows.count()):
            row = rows.nth(i)
            name_text = row.locator(ROW_SAMPLE_NAME_TD).inner_text().strip()
            if sample_name in name_text:
                return row
        return None

    def assign_sample(self, row: Locator, note: str) -> bool:
        """Click Assign on a row, fill note in modal, confirm, wait for close."""
        btn = row.get_by_role("button", name=ASSIGN_BUTTON_NAME)
        if btn.count() == 0:
            return False

        btn.first.evaluate("el => el.click()")
        self.wait_for_idle(1.5)

        modal = self.page.locator(ASSIGN_MODAL_SELECTOR)
        try:
            modal.wait_for(state="visible", timeout=10000)
        except Exception:
            return False

        note_input = modal.locator(NOTE_INPUT_SELECTOR)
        if note_input.count() > 0:
            note_input.first.fill(note)
            self.wait_for_idle(1)

        modal.get_by_role("button", name=MODAL_ASSIGN_BUTTON_NAME).evaluate("el => el.click()")
        self.wait_for_idle(2)

        try:
            modal.wait_for(state="detached", timeout=30000)
            return True
        except Exception:
            return False
