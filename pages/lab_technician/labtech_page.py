import random
import time
from typing import Optional, List, Dict
from playwright.sync_api import Locator
from pages.base_page import BasePage
from locators.lab_technician.labtech_locators import (
    REPORT_ENTRY_TEXT,
    DATE_INPUT_SELECTOR,
    SEARCH_NAME_NTH,
    SEARCH_MOBILE_NTH,
    SEARCH_TEXTBOX_NAME,
    APPLY_FILTER_TEXT,
    DEPT_DROPDOWN_TEXT,
    DEPT_OPTION_TEMPLATE,
    TABLE_ROWS_SELECTOR,
    REPORT_ENTRY_ICON_ALT,
    SAMPLE_SUB_ROW_SELECTOR,
    ACCEPT_ACTION_TEXT,
    REJECT_ACTION_TEXT,
    REFRESH_ACTION_TEXT,
    REJECTION_MODAL_SELECTOR,
    REJECTION_SEND_BUTTON_NAME,
    PREV_SUB_DEPT_BUTTON_NAME,
    NEXT_SUB_DEPT_BUTTON_NAME,
    TEST_HEADING_TEMPLATE,
    TEST_ROW_XPATH,
    PARAM_CONTAINER_XPATH,
    PARAM_INPUT_SELECTOR,
    SAVE_BUTTON_NAME,
    CONFIRM_YES_BUTTON_NAME,
    RESAMPLE_BUTTON_NAME,
    RESAMPLE_REASON_XPATH_TEMPLATE,
    ADD_SUBMIT_BUTTON_NAME,
)


class LabTechPage(BasePage):
    """Page object for the Lab Technician Report Entry workflow."""

    def wait_for_report_entry_visible(self) -> bool:
        """Wait until 'Report Entry' menu is visible; returns False on timeout."""
        try:
            self.page.get_by_text(
                REPORT_ENTRY_TEXT, exact=True
            ).wait_for(state="visible", timeout=10000)
            return True
        except Exception:
            return False

    def click_report_entry_menu(self) -> None:
        """Click the 'Report Entry' navigation menu item."""
        self.page.get_by_text(REPORT_ENTRY_TEXT, exact=True).click()
        self.wait_for_idle(2)

    def apply_date_filters(self, from_date: str, to_date: str) -> None:
        """Fill AntD RangePicker date inputs (DD/MM/YYYY or YYYY-MM-DD, Tab-separated)."""
        def _to_dmy(d: str) -> str:
            if "/" in d:
                return d  # already DD/MM/YYYY
            y, m, day = d.split("-")
            return f"{day}/{m}/{y}"

        from_dmy = _to_dmy(from_date)
        to_dmy = _to_dmy(to_date)
        date_input = self.page.locator(DATE_INPUT_SELECTOR)
        date_input.first.click(click_count=3)
        self.wait_for_idle(0.2)
        self.page.keyboard.type(from_dmy)
        self.wait_for_idle(0.3)
        self.page.keyboard.press("Tab")
        self.wait_for_idle(0.2)
        self.page.keyboard.type(to_dmy)
        self.wait_for_idle(0.3)
        self.page.keyboard.press("Tab")
        self.wait_for_idle(0.5)

    def select_department(self, department: str) -> None:
        """Select department from the first 'None' dropdown."""
        dropdown = self.page.locator("span").filter(has_text=DEPT_DROPDOWN_TEXT).nth(0)
        dropdown.wait_for(state="visible", timeout=5000)
        dropdown.click()
        self.wait_for_idle(1)
        self.page.get_by_text(department, exact=True).click()
        self.wait_for_idle(1)

    def select_sub_department(self, sub_department: str) -> None:
        """Select sub-department by typing first 3 chars to filter, then clicking exact match."""
        dropdown = self.page.locator("span").filter(has_text=DEPT_DROPDOWN_TEXT).nth(0)
        dropdown.wait_for(state="visible", timeout=5000)
        dropdown.click()
        self.wait_for_idle(0.5)

        self.page.keyboard.type(sub_department[:3])
        self.wait_for_idle(0.5)

        option_selector = DEPT_OPTION_TEMPLATE.format(dept=sub_department)
        self.page.locator(option_selector).wait_for(state="visible", timeout=5000)
        self.page.locator(option_selector).click()
        self.wait_for_idle(1)

    def fill_search_name(self, name: str) -> None:
        """Fill patient name in the search filter."""
        self.page.get_by_role(
            "textbox", name=SEARCH_TEXTBOX_NAME
        ).nth(SEARCH_NAME_NTH).fill(name)
        self.wait_for_idle(0.3)

    def fill_search_mobile(self, mobile: str) -> None:
        """Fill mobile number in the search filter."""
        self.page.get_by_role(
            "textbox", name=SEARCH_TEXTBOX_NAME
        ).nth(SEARCH_MOBILE_NTH).fill(mobile)
        self.wait_for_idle(0.3)

    def click_apply_filter(self) -> None:
        """Click 'Apply Filter' and wait for results to load."""
        self.page.get_by_text(APPLY_FILTER_TEXT, exact=True).click()
        self.page.wait_for_load_state("networkidle")
        self.wait_for_idle(2)

    def wait_for_patient_rows(self) -> bool:
        """Wait for patient result rows to appear; returns False on timeout."""
        try:
            self.page.locator(TABLE_ROWS_SELECTOR).first.wait_for(
                state="visible", timeout=10000
            )
            return True
        except Exception:
            return False

    def find_sample_sub_row_by_name(
        self, sample_name: str, anchor_id: Optional[str] = None
    ) -> Optional[Locator]:
        """Find sample sub-row by name; when anchor_id given, restricts to that patient row."""
        rows = self.page.locator(TABLE_ROWS_SELECTOR)
        for row_idx in range(rows.count()):
            row = rows.nth(row_idx)
            row_text = row.inner_text()

            if anchor_id and anchor_id not in row_text:
                continue

            sub_rows = row.locator(SAMPLE_SUB_ROW_SELECTOR)
            for sub_idx in range(sub_rows.count()):
                sub_row = sub_rows.nth(sub_idx)
                text = sub_row.inner_text()
                if sample_name in text:
                    return sub_row
        return None

    def find_sample_sub_row(
        self, sample_name: str, sample_id: str
    ) -> Optional[Locator]:
        """Find the sub-row matching both sample_name and sample_id."""
        rows = self.page.locator(TABLE_ROWS_SELECTOR)
        row_count = rows.count()

        for row_idx in range(row_count):
            row = rows.nth(row_idx)
            sub_rows = row.locator(SAMPLE_SUB_ROW_SELECTOR)

            for sub_idx in range(sub_rows.count()):
                sub_row = sub_rows.nth(sub_idx)
                try:
                    # Short timeout: under heavy load the table can re-render
                    # between count() and nth(); skip stale sub-rows instead
                    # of letting a 30 s default-timeout fail the whole step.
                    text = sub_row.inner_text(timeout=5000)
                except Exception:
                    continue

                if sample_name in text and sample_id in text:
                    return sub_row

        return None

    def find_sample_sub_row_by_action(
        self,
        sample_name: str,
        action_text: str,
        anchor_id: Optional[str] = None,
    ) -> Optional[Locator]:
        """Find sub-row by sample_name + action button text (fallback for stale IDs)."""
        rows = self.page.locator(TABLE_ROWS_SELECTOR)
        for row_idx in range(rows.count()):
            row = rows.nth(row_idx)
            row_text = row.inner_text()

            if anchor_id and anchor_id not in row_text:
                continue

            sub_rows = row.locator(SAMPLE_SUB_ROW_SELECTOR)
            for sub_idx in range(sub_rows.count()):
                sub_row = sub_rows.nth(sub_idx)
                text = sub_row.inner_text()
                if sample_name in text and action_text in text:
                    return sub_row
        return None

    def click_accept_sample(self, sub_row: Locator) -> None:
        """Click Accept on a sample sub-row."""
        sub_row.locator("span").filter(has_text=ACCEPT_ACTION_TEXT).click()
        self.page.wait_for_load_state("networkidle", timeout=15000)
        self.wait_for_idle(1)

    def click_refresh_sample(self, sub_row: Locator) -> None:
        """Click Refresh on a sample sub-row."""
        sub_row.locator("span").filter(has_text=REFRESH_ACTION_TEXT).click()
        self.wait_for_idle(1)

    def click_reject_sample(self, sub_row: Locator) -> None:
        """Click Reject on a sample sub-row (opens rejection modal)."""
        sub_row.locator("span").filter(has_text=REJECT_ACTION_TEXT).click()
        self.wait_for_idle(0.8)

    def handle_rejection_modal(self, rejection_config: Dict) -> bool:
        """Complete the rejection modal; returns False if modal not found."""
        modal = self.page.locator(REJECTION_MODAL_SELECTOR)
        try:
            modal.wait_for(state="visible", timeout=5000)
        except Exception:
            return False

        action_done = False
        sub_dept = rejection_config.get("sub_department")
        if sub_dept:
            dept_el = modal.locator(f':text-is("{sub_dept}")')
            if dept_el.count() > 0:
                dept_el.click()
                self.wait_for_idle(0.5)
                count = rejection_config.get("select_random_reasons", 2)
                checkboxes = modal.get_by_role("checkbox")
                total = checkboxes.count()
                if total > 0:
                    picks = random.sample(range(total), min(count, total))
                    for idx in picks:
                        checkboxes.nth(idx).check()
                    action_done = True

        if not action_done:
            reason = rejection_config.get("rejection_reason", "Rejected")
            modal.get_by_role("textbox").fill(reason)

        modal.get_by_role("button", name=REJECTION_SEND_BUTTON_NAME).click()
        self.wait_for_idle(1.5)
        return True

    def open_report_entry(self, sample_id: Optional[str] = None) -> bool:
        """Hover the target row until Report Entry icon appears and click it.

        When sample_id is given, scans sub-rows to pick the correct patient row.
        Falls back to first row if not found. Scrolls up to 10 times if needed.
        """
        rows = self.page.locator(TABLE_ROWS_SELECTOR)

        target_row = rows.first
        if sample_id:
            found = False
            for i in range(rows.count()):
                r = rows.nth(i)
                sub_rows = r.locator(SAMPLE_SUB_ROW_SELECTOR)
                for j in range(sub_rows.count()):
                    try:
                        # Short timeout: under heavy load the table can
                        # re-render between count() and nth(); skip stale
                        # sub-rows instead of timing out the whole step.
                        text = sub_rows.nth(j).inner_text(timeout=5000)
                    except Exception:
                        continue
                    if sample_id in text:
                        target_row = r
                        found = True
                        break
                if found:
                    break
            if not found:
                target_row = rows.last  # table sorted ASC; last = newest

        for _ in range(10):
            target_row.hover()
            self.wait_for_idle(0.3)

            icon = target_row.locator(f"img[alt='{REPORT_ENTRY_ICON_ALT}']")
            if icon.count() > 0:
                icon.first.click()
                self.wait_for_idle(3)
                return True

            self.scroll_down(400)
            self.wait_for_idle(0.4)

        return False

    def reset_to_first_sub_department(self) -> None:
        """Click Previous Sub-Department until disabled to start from the first."""
        prev_btn = self.page.get_by_role(
            "button", name=PREV_SUB_DEPT_BUTTON_NAME
        )
        while prev_btn.is_enabled():
            prev_btn.click()
            self.wait_for_idle(1.2)

    def click_next_sub_department(self) -> bool:
        """Click Next Sub-Department; returns False if already at the last."""
        next_btn = self.page.get_by_role(
            "button", name=NEXT_SUB_DEPT_BUTTON_NAME
        )
        if next_btn.is_enabled():
            next_btn.click()
            self.wait_for_idle(1.5)
            return True
        return False

    def _scroll_until_test_visible(
        self, test_name: str, max_scrolls: int = 8
    ) -> Optional[Locator]:
        """Scroll down until the test heading is visible."""
        selector = TEST_HEADING_TEMPLATE.format(test_name=test_name)
        locator = self.page.locator(selector)

        for _ in range(max_scrolls):
            if locator.count() > 0:
                return locator.first
            self.scroll_down(400)
            self.wait_for_idle(0.4)

        return None

    def find_test_row_on_current_page(self, test_name: str) -> Optional[Locator]:
        """Find test row on the current sub-department page by scrolling if needed."""
        heading = self._scroll_until_test_visible(test_name)
        if not heading:
            return None

        row = heading.locator(TEST_ROW_XPATH)
        if row.count() == 0:
            return None

        row.first.scroll_into_view_if_needed()
        self.wait_for_idle(0.3)
        return row.first

    def traverse_and_find_test(self, test_name: str) -> Optional[Locator]:
        """Reset to first sub-dept then traverse forward until test row is found."""
        self.reset_to_first_sub_department()

        while True:
            row = self.find_test_row_on_current_page(test_name)
            if row:
                return row

            if not self.click_next_sub_department():
                break

        return None

    def fill_parameter(self, row: Locator, param_name: str, value: str) -> bool:
        """Fill a single parameter input; returns False if label or input not found.

        Retries up to 3 times to handle DOM re-renders after save cycles —
        the second LFT save cycle was historically flaky here (P2 Bilirubin -
        Total). Stores diagnostic context on `self.last_param_fill_diag` so
        the flow can surface it in the failure message.
        """
        self.last_param_fill_diag: Optional[str] = None
        for attempt in range(3):
            try:
                row.scroll_into_view_if_needed()
            except Exception:
                pass
            self.wait_for_idle(0.5)

            label = row.get_by_text(param_name, exact=True)
            if label.count() == 0:
                label = row.get_by_text(param_name, exact=False)
            if label.count() == 0:
                self.last_param_fill_diag = f"label not found (attempt {attempt + 1}/3)"
                if attempt < 2:
                    self.wait_for_idle(2)
                    continue
                return False

            label_el = label.first
            try:
                label_el.scroll_into_view_if_needed()
            except Exception:
                pass
            self.wait_for_idle(0.2)

            container = label_el.locator(PARAM_CONTAINER_XPATH)
            textbox = container.locator(PARAM_INPUT_SELECTOR)

            if textbox.count() == 0:
                self.last_param_fill_diag = (
                    f"input not in container (attempt {attempt + 1}/3)"
                )
                if attempt < 2:
                    self.wait_for_idle(2)
                    continue
                return False

            if not self._wait_until_enabled(textbox.first, timeout=5.0):
                self.last_param_fill_diag = (
                    f"input still disabled after 5s (attempt {attempt + 1}/3)"
                )
                if attempt < 2:
                    self.wait_for_idle(2)
                    continue
                return False

            textbox.first.fill(str(value))
            self.wait_for_idle(0.2)
            return True
        return False

    def _wait_until_enabled(self, button: Locator, timeout: float = 10.0) -> bool:
        """Poll until button becomes enabled within timeout seconds."""
        start = time.time()
        while time.time() - start < timeout:
            if button.is_enabled():
                return True
            self.wait_for_idle(0.3)
        return False

    def save_test(self, row: Locator) -> bool:
        """Click Save and handle the Yes confirmation; returns False if button missing."""
        save_btn = row.get_by_role("button", name=SAVE_BUTTON_NAME)

        if save_btn.count() == 0:
            return False

        save_btn.first.scroll_into_view_if_needed()
        self.wait_for_idle(0.3)

        if not self._wait_until_enabled(save_btn.first):
            return False

        save_btn.first.evaluate("el => el.click()")
        self.wait_for_idle(1)

        # Handle confirmation dialog
        yes_btn = self.page.get_by_role(
            "button", name=CONFIRM_YES_BUTTON_NAME
        )
        if yes_btn.count() > 0:
            yes_btn.first.click()
            # Server can take several seconds; wait for dialog to fully close
            try:
                yes_btn.wait_for(state="hidden", timeout=60000)
            except Exception:
                pass
            # Fallback: Yes button text may change to "Loading…" before hidden
            try:
                self.page.wait_for_selector(
                    ".ant-modal-wrap", state="hidden", timeout=60000
                )
            except Exception:
                pass
            self.wait_for_idle(1)

        return True

    def resample_test(self, row: Locator, reason: str) -> bool:
        """Click Re-sample, fill reason, and submit; returns False if button missing."""
        btn = row.get_by_role("button", name=RESAMPLE_BUTTON_NAME)
        if btn.count() == 0:
            return False
        if btn.first.is_disabled():
            return False

        btn.first.scroll_into_view_if_needed()
        self.wait_for_idle(0.3)
        btn.first.click()
        self.wait_for_idle(1.5)
        option_xpath = RESAMPLE_REASON_XPATH_TEMPLATE.format(reason=reason)
        option = self.page.locator(option_xpath)
        if option.count() > 0:
            option.first.click()
        else:
            self.page.get_by_role("textbox").fill(reason)

        self.page.get_by_role(
            "button", name=ADD_SUBMIT_BUTTON_NAME
        ).click()
        self.wait_for_idle(2)
        return True
