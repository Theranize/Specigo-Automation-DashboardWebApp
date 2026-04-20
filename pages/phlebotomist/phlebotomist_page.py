"""Phlebotomist page object."""

from typing import Optional
from playwright.sync_api import Locator
from pages.base_page import BasePage
from locators.phlebotomist.phlebotomist_locators import (
    SIDEBAR_PHLEBOTOMISTS_TEXT,
    SIDEBAR_SAMPLE_TRACKER_TEXT,
    PAGE_HEADER_TEXT,
    DATE_INPUT_SELECTOR,
    SEARCH_NAME_LABEL,
    SEARCH_MOBILE_LABEL,
    SEARCH_ID_PLACEHOLDER,
    SEARCH_BUTTON_NAME,
    TABLE_ROWS_SELECTOR,
    SAMPLE_BLOCK_SELECTOR,
    TOGGLE_SWITCH_SELECTOR,
    TOGGLE_CHECKED_ATTR,
    TOGGLE_CHECKED_VALUE,
)


def _to_iso(date_str: str) -> str:
    """Convert DD/MM/YYYY → YYYY-MM-DD; passthrough if already ISO."""
    if "/" in date_str:
        d, m, y = date_str.split("/")
        return f"{y}-{m}-{d}"
    return date_str


class PhlebotomistPage(BasePage):
    """Page object for the Phlebotomist Sample Tracker workflow."""

    def navigate_to_sample_tracker(self) -> None:
        """Click Phlebotomists sidebar → Sample Tracker (hover + double-click to expand)."""
        phlebo = self.page.get_by_text(SIDEBAR_PHLEBOTOMISTS_TEXT, exact=True)
        phlebo.wait_for(state="visible", timeout=15000)
        phlebo.click()
        phlebo.hover()
        self.wait_for_idle(0.6)
        phlebo.click()

        self.page.get_by_text(
            SIDEBAR_SAMPLE_TRACKER_TEXT, exact=True
        ).click()
        self.wait_for_idle(2)

    def verify_page_header(self) -> bool:
        """Verify the Sample Tracker page header is visible."""
        header = self.page.get_by_text(PAGE_HEADER_TEXT, exact=True)
        try:
            header.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            return False

    def apply_date_filters(self, from_date: str, to_date: str) -> None:
        """Fill from_date and to_date inputs. Accepts DD/MM/YYYY or YYYY-MM-DD."""
        self.page.locator(DATE_INPUT_SELECTOR).nth(0).fill(_to_iso(from_date))
        self.page.locator(DATE_INPUT_SELECTOR).nth(1).fill(_to_iso(to_date))

    def fill_search_name(self, name: str) -> None:
        """Fill patient name in the search filter."""
        self.page.get_by_role("textbox", name=SEARCH_NAME_LABEL).fill(name)

    def fill_search_mobile(self, mobile: str) -> None:
        """Fill mobile number in the search filter."""
        self.page.get_by_role(
            "textbox", name=SEARCH_MOBILE_LABEL
        ).fill(mobile)

    def fill_search_id(self, sample_id: str) -> None:
        """Clear and fill the sample ID search field."""
        id_input = self.page.get_by_placeholder(
            SEARCH_ID_PLACEHOLDER
        ).nth(1)
        id_input.fill("")
        id_input.fill(sample_id)

    def click_search(self) -> None:
        """Click Search button and wait for table to load."""
        self.page.get_by_role("button", name=SEARCH_BUTTON_NAME).click()
        self.page.wait_for_load_state("networkidle")
        self.wait_for_idle(1.5)

    def find_sample_block(self, sample_name: str, sample_id: str) -> Optional[Locator]:
        """Find sample block matching both sample_name AND sample_id."""
        rows = self.page.locator(TABLE_ROWS_SELECTOR)
        try:
            rows.first.wait_for(state="visible", timeout=8000)
        except Exception:
            return None
        self.wait_for_idle(5)
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

    def toggle_sample(self, block: Locator, action: str) -> str:
        """Toggle switch in sample block; returns toggled_on/toggled_off/already_on/already_off."""
        toggle = block.locator(TOGGLE_SWITCH_SELECTOR)
        toggle.wait_for(state="visible", timeout=3000)
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
