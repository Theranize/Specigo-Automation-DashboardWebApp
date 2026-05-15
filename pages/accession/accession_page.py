"""Accession page object — Sample Verification workflow."""

import random
from typing import Optional, Dict
from playwright.sync_api import Locator
from pages.base_page import BasePage


def _to_iso(date_str: str) -> str:
    """Convert DD/MM/YYYY → YYYY-MM-DD; passthrough if already ISO."""
    if "/" in date_str:
        d, m, y = date_str.split("/")
        return f"{y}-{m}-{d}"
    return date_str
from locators.accession.accession_locators import (
    SIDEBAR_ACCESSION_TEXT,
    SIDEBAR_SAMPLE_VERIFICATION_TEXT,
    DATE_INPUT_SELECTOR,
    SEARCH_NAME_PLACEHOLDER,
    SEARCH_NAME_NTH,
    SEARCH_MOBILE_NTH,
    SEARCH_BUTTON_NAME,
    TABLE_ROWS_SELECTOR,
    SAMPLE_BLOCK_SELECTOR,
    SAMPLE_NAME_SELECTOR,
    SAMPLE_ID_SELECTOR,
    REFRESH_ACTION_XPATH,
    ACCEPT_ACTION_XPATH,
    REJECT_ACTION_XPATH,
    REJECTION_MODAL_SELECTOR,
    REJECTION_CHECKBOX_SELECTOR,
    REJECTION_EDITOR_NAME,
    REJECTION_SEND_BUTTON_NAME,
)


class AccessionPage(BasePage):
    """Page object for the Accession Sample Verification workflow."""

    def navigate_to_sample_verification(self) -> None:
        """Navigate to Accession Sample Verification (URL: /sampleverification).

        Bypasses the sidebar nav menu (Accession → Sample Verification),
        which is fragile under heavy parallel load — the menu's expand
        animation often doesn't complete and the sub-link stays hidden.
        Direct goto is deterministic.
        """
        base = getattr(self.page.context, "base_url", "") or ""
        if "sampleverification" not in (self.page.url or ""):
            self.safe_goto(base + "sampleverification")
        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        try:
            self.page.get_by_placeholder(SEARCH_NAME_PLACEHOLDER).first.wait_for(
                state="visible", timeout=20000
            )
        except Exception:
            pass
        self.wait_for_idle(2)

    def wait_for_table_rows(self) -> bool:
        """Wait for result table rows to appear; returns True if rows appeared.

        Bumped to 30 s — under 5-worker parallel load the dev backend's
        search response can take 15-20 s; the previous 10 s was tripping
        false-negatives on otherwise-valid runs.
        """
        try:
            self.page.locator(TABLE_ROWS_SELECTOR).first.wait_for(
                state="visible", timeout=30000
            )
            return True
        except Exception:
            return False

    def apply_date_filters(self, from_date: str, to_date: str) -> None:
        """Fill from_date and to_date inputs. Accepts DD/MM/YYYY or YYYY-MM-DD."""
        self.page.locator(DATE_INPUT_SELECTOR).nth(0).fill(_to_iso(from_date))
        self.page.locator(DATE_INPUT_SELECTOR).nth(1).fill(_to_iso(to_date))

    def fill_search_name(self, name: str) -> None:
        """Enter patient name in the search filter."""
        self.page.get_by_placeholder(
            SEARCH_NAME_PLACEHOLDER
        ).nth(SEARCH_NAME_NTH).fill(name)

    def fill_search_mobile(self, mobile: str) -> None:
        """Enter mobile number in the search filter."""
        self.page.get_by_placeholder(
            SEARCH_NAME_PLACEHOLDER
        ).nth(SEARCH_MOBILE_NTH).fill(mobile)

    def click_search(self) -> None:
        """Click Search button and wait for table to load."""
        self.page.get_by_role("button", name=SEARCH_BUTTON_NAME).click()
        self.page.wait_for_load_state("networkidle")
        self.wait_for_idle(1.5)

    def find_sample_block(
        self, sample_name: str, sample_id: str
    ) -> Optional[Locator]:
        """Find the sample block where BOTH sample_name AND sample_id match."""
        rows = self.page.locator(TABLE_ROWS_SELECTOR)
        try:
            rows.first.wait_for(state="visible", timeout=8000)
        except Exception:
            return None
        row_count = rows.count()

        for row_idx in range(row_count):
            row = rows.nth(row_idx)
            blocks = row.locator(SAMPLE_BLOCK_SELECTOR)

            for block_idx in range(blocks.count()):
                block = blocks.nth(block_idx)
                block_text = block.inner_text()

                if sample_name in block_text and sample_id in block_text:
                    return block

        return None

    def find_sample_block_by_name(
        self,
        sample_name: str,
        preferred_sample_id: Optional[str] = None,
    ) -> Optional[Locator]:
        """Find a sample block by name (recollected samples have new IDs).

        If `preferred_sample_id` is given, prefer the row whose text contains
        it; this defends against concurrent same-mobile tests both reaching
        the recollection step and seeing each other's rows. Falls back to
        name-only first match if the hint doesn't resolve.
        """
        rows = self.page.locator(TABLE_ROWS_SELECTOR)
        try:
            rows.first.wait_for(state="visible", timeout=8000)
        except Exception:
            return None
        row_count = rows.count()
        if preferred_sample_id:
            for row_idx in range(row_count):
                row = rows.nth(row_idx)
                if preferred_sample_id in row.inner_text():
                    blocks = row.locator(SAMPLE_BLOCK_SELECTOR)
                    for block_idx in range(blocks.count()):
                        block = blocks.nth(block_idx)
                        if sample_name in block.inner_text():
                            return block
        for row_idx in range(row_count):
            row = rows.nth(row_idx)
            blocks = row.locator(SAMPLE_BLOCK_SELECTOR)
            for block_idx in range(blocks.count()):
                block = blocks.nth(block_idx)
                if sample_name in block.inner_text():
                    return block
        return None

    def click_refresh(self, block: Locator) -> None:
        """Click Refresh action inside the matched block."""
        refresh_btn = block.locator(REFRESH_ACTION_XPATH)
        refresh_btn.wait_for(state="visible", timeout=3000)
        refresh_btn.click()
        self.wait_for_idle(2)

    def click_accept(self, block: Locator) -> None:
        """Click Accept action inside the matched block."""
        accept_btn = block.locator(ACCEPT_ACTION_XPATH)
        accept_btn.wait_for(state="visible", timeout=3000)
        accept_btn.click()
        self.wait_for_idle(2)

    def click_reject(self, block: Locator) -> None:
        """Click Reject action inside the matched block."""
        reject_btn = block.locator(REJECT_ACTION_XPATH)
        reject_btn.wait_for(state="visible", timeout=3000)
        reject_btn.click()
        self.wait_for_idle(2)

    def wait_for_rejection_modal(self) -> Optional[Locator]:
        """Wait for the rejection modal to appear; returns modal locator or None."""
        modal = self.page.locator(REJECTION_MODAL_SELECTOR)
        try:
            modal.wait_for(state="visible", timeout=5000)
            return modal
        except Exception:
            return None

    def handle_rejection_modal(
        self, modal: Locator, rejection_config: Dict
    ) -> bool:
        """Complete the rejection modal form and confirm Send."""
        sub_dept = rejection_config["sub_department"]
        modal.get_by_text(sub_dept, exact=True).click()
        self.wait_for_idle(1)

        count = rejection_config["select_random_reasons"]
        checkboxes = modal.locator(REJECTION_CHECKBOX_SELECTOR)
        total = checkboxes.count()

        if total > 0:
            indices = random.sample(
                range(total), min(count, total)
            )
            for idx in indices:
                checkboxes.nth(idx).click()
                self.wait_for_idle(0.3)

        reason_text = rejection_config["reason_text"]
        editor = modal.get_by_role("textbox", name=REJECTION_EDITOR_NAME)
        editor.click()
        editor.fill(reason_text)
        self.wait_for_idle(1)

        send_btn = modal.get_by_role("button", name=REJECTION_SEND_BUTTON_NAME)
        send_btn.evaluate("el => el.click()")
        self.page.wait_for_load_state("networkidle", timeout=20000)
        self.wait_for_idle(3)

        try:
            modal.wait_for(state="hidden", timeout=10000)
            return True
        except Exception:
            try:
                modal.wait_for(state="detached", timeout=5000)
                return True
            except Exception:
                return not modal.is_visible()
