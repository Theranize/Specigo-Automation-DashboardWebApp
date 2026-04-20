import time
from typing import Optional, Dict
from playwright.sync_api import Locator
from pages.base_page import BasePage
from locators.doctor.doctor_locators import (
    REPORT_ENTRY_TEXT,
    DATE_INPUT_SELECTOR,
    SEARCH_NAME_NTH,
    SEARCH_MOBILE_NTH,
    SEARCH_TEXTBOX_NAME,
    APPLY_FILTER_TEXT,
    TABLE_ROWS_SELECTOR,
    REPORT_ENTRY_ICON_ALT,
    NEXT_SUB_DEPT_BUTTON_NAME,
    PREV_SUB_DEPT_BUTTON_NAME,
    TEST_HEADING_TEMPLATE,
    TEST_ROW_XPATH,
    PARAM_CONTAINER_XPATH,
    PARAM_INPUT_SELECTOR,
    SAVE_BUTTON_NAME,
    CONFIRM_YES_BUTTON_NAME,
    APPROVE_BUTTON_NAME,
    FULLY_APPROVE_BUTTON_NAME,
    PARTIALLY_APPROVE_BUTTON_NAME,
    RETEST_BUTTON_NAME,
    RESAMPLE_FILTER_TEXT,
    ADD_SUBMIT_BUTTON_NAME,
    RECTIFY_BUTTON_NAME,
    RECTIFY_SUBMIT_SPAN,
    RECTIFY_REASON_TEXTBOX_NAME,
)


class DoctorPage(BasePage):
    """Page object for the Doctor Report Review workflow."""

    def wait_for_report_entry_visible(self) -> bool:
        """Wait until 'Report Entry' menu is visible; returns False on timeout."""
        try:
            self.page.get_by_text(
                REPORT_ENTRY_TEXT, exact=True
            ).wait_for(state="visible", timeout=30000)
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

    def open_report_entry(self, sample_id: Optional[str] = None) -> bool:
        """Hover the target row and click Report Entry icon.

        If sample_id is provided, finds the row containing that ID to avoid
        selecting the wrong patient when parallel runs share the same mobile number.
        Falls back to rows.first (newest) if no match found.
        """
        rows = self.page.locator(TABLE_ROWS_SELECTOR)

        try:
            rows.first.wait_for(state="visible", timeout=8000)
        except Exception:
            return False

        # Match by sample_id when available (parallel-run safety)
        target_row = None
        if sample_id:
            for i in range(rows.count()):
                row = rows.nth(i)
                if sample_id in row.inner_text():
                    target_row = row
                    break
        if target_row is None:
            target_row = rows.first

        for _ in range(10):
            target_row.hover()
            self.wait_for_idle(0.3)
            icon = target_row.locator(f"img[alt='{REPORT_ENTRY_ICON_ALT}']").first
            if icon.count() > 0:
                icon.click()
                self.wait_for_idle(3)
                return True
            self.scroll_down(400)
            self.wait_for_idle(0.4)

        return False

    def is_sub_dept_visible(self, sub_dept_name: str) -> bool:
        """Check if a sub-department heading is currently visible."""
        return self.page.get_by_role("heading", name=sub_dept_name).count() > 0

    def navigate_to_sub_dept(self, sub_dept_name: str) -> bool:
        """Navigate Next/Previous until sub-dept heading is visible (max 20 attempts)."""
        for _ in range(20):
            if self.is_sub_dept_visible(sub_dept_name):
                return True

            next_btn = self.page.get_by_role("button", name=NEXT_SUB_DEPT_BUTTON_NAME)
            prev_btn = self.page.get_by_role("button", name=PREV_SUB_DEPT_BUTTON_NAME)

            if next_btn.is_enabled():
                next_btn.click()
            elif prev_btn.is_enabled():
                prev_btn.click()

            self.wait_for_idle(1.5)

        return False

    def find_test_row(self, test_name: str, max_scrolls: int = 10) -> Optional[Locator]:
        """Locate test row in the current sub-department by scrolling if needed."""
        selector = TEST_HEADING_TEMPLATE.format(test_name=test_name)

        for _ in range(max_scrolls):
            heading = self.page.locator(selector)
            if heading.count() > 0:
                row = heading.first.locator(TEST_ROW_XPATH)
                if row.count() > 0:
                    row.first.scroll_into_view_if_needed()
                    self.wait_for_idle(0.3)
                    return row.first
            self.scroll_down(400)
            self.wait_for_idle(0.4)

        return None

    def fill_parameter(self, row: Locator, param_name: str, value: str) -> bool:
        """Fill a single parameter input; returns False if label or input not found.

        Retries up to 3 times with 2s waits to handle temporarily-disabled inputs
        that occur during page re-renders after save/approve cycles.
        """
        for attempt in range(3):
            label = row.get_by_text(param_name, exact=True)
            if label.count() == 0:
                label = row.get_by_text(param_name, exact=False)
            if label.count() == 0:
                if attempt < 2:
                    self.wait_for_idle(2)
                    continue
                return False

            container = label.locator(PARAM_CONTAINER_XPATH)
            textbox = container.locator(PARAM_INPUT_SELECTOR)

            if textbox.count() == 0 or textbox.first.is_disabled():
                if attempt < 2:
                    self.wait_for_idle(2)
                    continue
                return False

            textbox.first.click()
            textbox.first.fill("")      # clear → triggers React onChange (dirty state)
            textbox.first.type(str(value), delay=50)
            self.wait_for_idle(0.2)
            return True
        return False

    def fill_parameters(self, row: Locator, parameters: Dict) -> Optional[str]:
        """Fill all parameter inputs; returns None on success, error string on failure."""
        for param_name, value in parameters.items():
            if not self.fill_parameter(row, param_name, value):
                return f"Parameter fill failed: {param_name}"
        return None

    def _wait_until_enabled(self, button: Locator, timeout: float = 10.0) -> bool:
        """Poll until button becomes enabled within timeout seconds."""
        start = time.time()
        while time.time() - start < timeout:
            if button.is_enabled():
                return True
            self.wait_for_idle(0.3)
        return False

    def save_test(self, row: Locator) -> bool:
        """Click Save and handle Yes confirmation; returns False if button missing.

        Some test layouts (e.g. 24-hr urine tests with Normal/Abnormal radio rows)
        render the action buttons in a following sibling <tr> rather than the same
        <tr> as the heading.  We try the row scope first, then fall back to sibling rows.
        """
        save_btn = row.get_by_role("button", name=SAVE_BUTTON_NAME)

        try:
            save_btn.first.wait_for(state="attached", timeout=3000)
        except Exception:
            # Button not in the heading's ancestor <tr> — look in following sibling rows
            save_btn = row.locator("xpath=following-sibling::tr").get_by_role(
                "button", name=SAVE_BUTTON_NAME
            )
            try:
                save_btn.first.wait_for(state="attached", timeout=10000)
            except Exception:
                return False

        save_btn.first.scroll_into_view_if_needed()
        self.wait_for_idle(0.3)

        if not self._wait_until_enabled(save_btn.first, timeout=30.0):
            return False

        save_btn.first.click()

        # Wait for the confirmation dialog Yes button to become visible
        yes_btn = self.page.get_by_role("button", name=CONFIRM_YES_BUTTON_NAME)
        try:
            yes_btn.wait_for(state="visible", timeout=8000)
        except Exception:
            # No dialog — save completed without a confirmation prompt
            self.wait_for_idle(1.0)
            return True

        # Use JS click to ensure the click registers regardless of AntD overlay state
        yes_btn.first.evaluate("el => el.click()")

        # Wait for Yes button to detach (API call complete, dialog closed)
        try:
            yes_btn.first.wait_for(state="detached", timeout=120000)
        except Exception:
            pass

        # Wait for the modal to fully disappear before proceeding
        dialog = self.page.get_by_role("dialog")
        try:
            dialog.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass

        self.wait_for_idle(2.0)
        return True

    def handle_approve(self, row: Locator, action: str) -> bool:
        """Click Approve then Fully or Partially Approve based on action."""
        approve_btn = row.get_by_role("button", name=APPROVE_BUTTON_NAME)

        if approve_btn.count() == 0:
            return False

        approve_btn.first.scroll_into_view_if_needed()
        self.wait_for_idle(1.0)

        if not self._wait_until_enabled(approve_btn.first):
            return False

        approve_btn.first.evaluate("el => el.click()")
        self.wait_for_idle(1.0)

        dialog = self.page.get_by_role("dialog")
        try:
            dialog.wait_for(state="visible", timeout=20000)
        except Exception:
            return False

        if action == "partial_approve":
            btn = dialog.get_by_role("button", name=PARTIALLY_APPROVE_BUTTON_NAME)
        else:
            btn = dialog.get_by_role("button", name=FULLY_APPROVE_BUTTON_NAME)
        try:
            btn.wait_for(state="visible", timeout=10000)
        except Exception:
            pass
        btn.evaluate("el => el.click()")

        self.wait_for_idle(4.0)
        return True

    def handle_retest(self, row: Locator) -> bool:
        """Click Re-Test and confirm Yes; returns False if button or dialog missing."""
        retest_btn = row.get_by_role("button", name=RETEST_BUTTON_NAME)

        if retest_btn.count() == 0:
            return False

        retest_btn.first.click()

        yes_btn = self.page.get_by_role("button", name=CONFIRM_YES_BUTTON_NAME)
        try:
            yes_btn.wait_for(state="visible", timeout=5000)
        except Exception:
            return False

        yes_btn.click()
        self.wait_for_idle(1.5)
        return True

    def handle_resample(self, row: Locator, reason: str) -> bool:
        """Click Re-sample, select reason (checkbox or textbox), and submit."""
        btn = row.locator("button").filter(has_text=RESAMPLE_FILTER_TEXT)

        if btn.count() == 0:
            return False

        btn.first.scroll_into_view_if_needed()
        self.wait_for_idle(0.3)

        if not self._wait_until_enabled(btn.first, timeout=15.0):
            return False

        btn.first.evaluate("el => el.click()")

        dialog = self.page.get_by_role("dialog")
        try:
            dialog.wait_for(state="visible", timeout=5000)
        except Exception:
            return False

        checkbox = dialog.get_by_label(reason)
        if checkbox.count() > 0:
            checkbox.first.check()
        else:
            dialog.get_by_role("textbox").first.fill(reason)

        self.page.get_by_role("button", name=ADD_SUBMIT_BUTTON_NAME).click()
        self.wait_for_idle(1.5)
        return True

    def handle_rectify(self, row: Locator, rectification: Dict) -> bool:
        """Click Rectify → select reason → (if Others) fill textbox → Submit → Yes.

        Rectify button  : row.get_by_role('button', name='Rectify')
        Dialog          : page.get_by_role('dialog')
        Reason option   : dialog.get_by_text(reason, exact=True)
        Others textbox  : dialog.get_by_role('textbox', name='Enter The Reason')
        Submit          : dialog.locator('span:has-text("Submit")')
        Confirmation    : page.get_by_role('button', name='Yes')

        Reasons: 'Sample Not Sufficient' | 'Sample Not Accepted By Machine' |
                 'For Re-Confirmation Of Values' | 'Others'
        Textbox is filled only when reason == 'Others'.
        """
        # --- Locate and click Rectify button ---
        rectify_btn = row.get_by_role("button", name=RECTIFY_BUTTON_NAME)

        if rectify_btn.count() == 0:
            return False

        rectify_btn.first.scroll_into_view_if_needed()
        self.wait_for_idle(0.3)

        if not self._wait_until_enabled(rectify_btn.first):
            return False

        rectify_btn.first.evaluate("el => el.click()")
        self.wait_for_idle(1.0)

        # --- Wait for Rectify dialog ---
        dialog = self.page.get_by_role("dialog")
        try:
            dialog.wait_for(state="visible", timeout=20000)
        except Exception:
            return False

        # --- Select rectification reason ---
        reason = rectification.get("reason", "")
        dialog.get_by_text(reason, exact=True).click()
        self.wait_for_idle(0.5)

        # --- Fill Others textbox only when reason is 'Others' ---
        if reason == "Others":
            dialog.get_by_role(
                "textbox", name=RECTIFY_REASON_TEXTBOX_NAME
            ).fill(rectification.get("other_text", ""))
            self.wait_for_idle(0.5)

        # --- Submit and confirm ---
        dialog.locator(RECTIFY_SUBMIT_SPAN).click()

        yes_btn = self.page.get_by_role("button", name=CONFIRM_YES_BUTTON_NAME)
        try:
            yes_btn.wait_for(state="visible", timeout=5000)
        except Exception:
            return False

        yes_btn.click()
        self.wait_for_idle(2)
        return True
