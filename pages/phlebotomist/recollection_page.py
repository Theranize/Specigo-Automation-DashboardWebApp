"""Phlebotomist Re-Collection page object."""

from typing import Optional
from playwright.sync_api import Locator
from pages.base_page import BasePage


def _to_iso(date_str: str) -> str:
    """Convert DD/MM/YYYY → YYYY-MM-DD; passthrough if already ISO."""
    if "/" in date_str:
        d, m, y = date_str.split("/")
        return f"{y}-{m}-{d}"
    return date_str
from locators.phlebotomist.recollection_locators import (
    SIDEBAR_PHLEBOTOMISTS_TEXT,
    SIDEBAR_SAMPLE_TRACKER_TEXT,
    PAGE_HEADER_TEXT,
    RECOLLECTION_TAB_LOCATOR,
    ACTIVE_TAB_SELECTOR,
    DATE_INPUT_SELECTOR,
    SEARCH_NAME_LABEL,
    SEARCH_MOBILE_LABEL,
    SEARCH_BUTTON_NAME,
    TABLE_ROWS_SELECTOR,
    SUB_DEPT_LABEL_SELECTOR,
    SAMPLE_SECTION_ANCESTOR_XPATH,
    SAMPLE_BLOCK_SELECTOR,
    SAMPLE_TEXT_SELECTOR,
    TOGGLE_SWITCH_SELECTOR,
    TOGGLE_CHECKED_ATTR,
    TOGGLE_CHECKED_VALUE,
)


class RecollectionPage(BasePage):
    """Page object for the Phlebotomist Re-Collection tab workflow."""

    def navigate_to_sample_tracker(self) -> None:
        """Click Phlebotomists sidebar → Sample Tracker."""
        phlebo = self.page.get_by_text(SIDEBAR_PHLEBOTOMISTS_TEXT, exact=True)
        phlebo.wait_for(state="visible", timeout=5000)
        phlebo.click()
        phlebo.hover()
        self.wait_for_idle(0.6)
        phlebo.click()
        self.page.get_by_text(SIDEBAR_SAMPLE_TRACKER_TEXT, exact=True).click()
        self.wait_for_idle(2)

    def verify_page_header(self) -> bool:
        """Verify the Sample Tracker page header is visible."""
        header = self.page.get_by_text(PAGE_HEADER_TEXT, exact=True)
        try:
            header.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def switch_to_recollection_tab(self) -> None:
        """Click the Re-Collection tab and wait for it to become active."""
        self.page.locator(RECOLLECTION_TAB_LOCATOR).click()
        self.wait_for_idle(1.5)

    def apply_date_filters(self, from_date: str, to_date: str) -> None:
        """Fill from_date and to_date inputs. Accepts DD/MM/YYYY or YYYY-MM-DD."""
        self.page.locator(DATE_INPUT_SELECTOR).nth(0).fill(_to_iso(from_date))
        self.page.locator(DATE_INPUT_SELECTOR).nth(1).fill(_to_iso(to_date))

    def fill_search_name(self, name: str) -> None:
        """Enter patient name in the search filter."""
        self.page.get_by_role("textbox", name=SEARCH_NAME_LABEL).fill(name)

    def fill_search_mobile(self, mobile: str) -> None:
        """Enter mobile number in the search filter."""
        self.page.get_by_role("textbox", name=SEARCH_MOBILE_LABEL).fill(mobile)

    def click_search(self) -> None:
        """Click Search and wait for the table to load."""
        self.page.get_by_role("button", name=SEARCH_BUTTON_NAME).click()
        self.page.wait_for_load_state("networkidle")
        self.wait_for_idle(1.5)

    def wait_for_rows(self) -> bool:
        """Wait for rows in the active tab; returns True if visible."""
        try:
            active_tab = self.page.locator(ACTIVE_TAB_SELECTOR)
            active_tab.locator(TABLE_ROWS_SELECTOR).first.wait_for(
                state="visible", timeout=10000
            )
            return True
        except Exception:
            return False

    def find_sample_block(
        self, patient_name: str, sub_department: str, sample_name: str
    ) -> Optional[Locator]:
        """Find sample block by sub_department + sample_name (no sample_id).

        Prefers block with toggle OFF when multiple blocks share the same name
        (e.g. two Serum blocks after a doctor resample).
        """
        active_tab = self.page.locator(ACTIVE_TAB_SELECTOR)
        rows = active_tab.locator(TABLE_ROWS_SELECTOR).filter(
            has_text=patient_name
        )

        matching: list = []

        for r in range(rows.count()):
            row = rows.nth(r)

            sub_headers = row.locator(SUB_DEPT_LABEL_SELECTOR).filter(
                has_text=sub_department
            )

            for s in range(sub_headers.count()):
                sub_header = sub_headers.nth(s)

                sample_section = sub_header.locator(SAMPLE_SECTION_ANCESTOR_XPATH)
                blocks = sample_section.locator(SAMPLE_BLOCK_SELECTOR)

                for b in range(blocks.count()):
                    block = blocks.nth(b)

                    texts = block.locator(SAMPLE_TEXT_SELECTOR)
                    if texts.count() < 1:
                        continue

                    if texts.nth(0).inner_text().strip() == sample_name:
                        matching.append(block)

        if not matching:
            return None

        for block in matching:
            toggle = block.locator(TOGGLE_SWITCH_SELECTOR)
            if toggle.count() > 0:
                if toggle.get_attribute(TOGGLE_CHECKED_ATTR) != TOGGLE_CHECKED_VALUE:
                    return block

        return matching[0]  # all toggles ON — fall back to first

    def get_block_sample_id(self, block: Locator) -> Optional[str]:
        """Return sample ID from block (nth(1) of SAMPLE_TEXT_SELECTOR); None if missing."""
        texts = block.locator(SAMPLE_TEXT_SELECTOR)
        if texts.count() < 2:
            return None
        raw = texts.nth(1).inner_text().strip()
        return raw if raw else None

    def toggle_sample(self, block: Locator, action: str) -> str:
        """Toggle the switch; returns toggled_on/toggled_off/already_on/already_off."""
        toggle = block.locator(TOGGLE_SWITCH_SELECTOR)
        toggle.wait_for(state="attached", timeout=5000)
        is_on = toggle.get_attribute(TOGGLE_CHECKED_ATTR) == TOGGLE_CHECKED_VALUE

        if action == "toggle_on" and not is_on:
            toggle.click()
            self.wait_for_idle(1)
            return "toggled_on"
        elif action == "toggle_off" and is_on:
            toggle.click()
            self.wait_for_idle(1)
            return "toggled_off"
        elif action == "toggle_on" and is_on:
            return "already_on"
        else:
            return "already_off"
