"""Front Desk page object — patient registration and published reports."""

import time
from typing import List, Dict, Optional
from pages.base_page import BasePage
from locators.front_desk.front_desk_locators import (
    ADD_PATIENT_BUTTON_TEXT,
    NEXT_BUTTON_NAME,
    SUBMIT_BUTTON_NAME,
    PRINT_BILL_BUTTON_NAME,
    PRINT_BARCODE_BUTTON_NAME,
    SEARCH_MOBILE_INPUT,
    SEARCH_BUTTON_NAME,
    ADD_RELATIVE_TEXT,
    RISK_LEVEL_DEFAULT,
    SALUTATION_LABEL_TEXT,
    SALUTATION_OPTION_XPATH,
    FIRST_NAME_PLACEHOLDER,
    MIDDLE_NAME_PLACEHOLDER,
    LAST_NAME_PLACEHOLDER,
    AGE_PLACEHOLDER,
    PIN_CODE_PLACEHOLDER,
    ADDRESS_PLACEHOLDER,
    EMAIL_PLACEHOLDER,
    MOBILE_INPUT,
    RELATION_LABEL_TEXT,
    RELATION_LABEL_CONTAINS,
    RELATION_OPTION_XPATH,
    TEST_SEARCH_COMBOBOX_ROLE,
    PAYMENT_AMOUNT_PLACEHOLDER,
    BALANCE_INPUT,
    FIRST_MODAL_CLOSE_XPATH,
    FIRST_MODAL_SELECTOR,
    FINAL_MODAL_CLOSE_SELECTOR,
    FINAL_MODAL_SELECTOR,
    SAMPLE_SUB_DEPT_SEPARATOR,
    SAMPLE_ID_FOLLOWING_XPATH,
    PUBLISHED_REPORTS_SIDEBAR_TEXT,
    PUBLISHED_REPORTS_TABLE_ROWS,
    VIEW_REPORT_BUTTON_NAME,
    DOWNLOAD_REPORT_BUTTON_NAME,
)
from playwright.sync_api import Locator


def _get_search_term(test_name: str) -> str:
    """Extract search term from test name for AntD combobox (up to 4 words)."""
    clean = test_name.split("(")[0].strip()
    words = clean.split()
    return " ".join(words[:4])


class FrontDeskPage(BasePage):
    """Page object for the Front Desk patient registration workflow."""

    def click_add_patient(self) -> None:
        """Click 'Add Patient' CTA and wait for geninfo page."""
        self.page.click(f'button:has-text("{ADD_PATIENT_BUTTON_TEXT}")')
        self.wait_for_navigation("**/geninfo")
        self.wait_for_idle(2)

    def select_risk_level(self, risk_level: str) -> None:
        """Click the risk level text on the geninfo page."""
        if risk_level and risk_level != RISK_LEVEL_DEFAULT:
            self.page.get_by_text(risk_level, exact=False).click()
            self.wait_for_idle(2)

    def click_next(self) -> None:
        """Scroll page down and click the Next button via JS dispatch.

        Waits a short interval after the click so AntD has time to render any
        per-field validation errors (the 'has-error' state gets applied on
        the next React tick — without this wait, a same-frame call to
        ``detect_error()`` from the flow returns None and the validation is
        silently bypassed).
        """
        self.scroll_down(800)
        next_btn = self.page.get_by_role("button", name=NEXT_BUTTON_NAME)
        next_btn.scroll_into_view_if_needed()
        self.wait_for_idle(1)
        next_btn.evaluate("el => el.click()")
        self.wait_for_idle(0.5)
        self.wait_for_idle(3)

    def click_submit(self) -> None:
        """Click Submit and wait for network to settle."""
        btn = self.page.get_by_role("button", name=SUBMIT_BUTTON_NAME)
        btn.evaluate("el => el.click()")
        self.page.wait_for_load_state("networkidle")

    def search_mobile(self, mobile: str) -> None:
        """Enter mobile number in the search phone field."""
        phone_input = self.page.locator(SEARCH_MOBILE_INPUT).nth(0)
        phone_input.wait_for(state="visible", timeout=10000)
        phone_input.click()
        phone_input.press("Control+A")
        phone_input.press("Backspace")
        phone_input.type(mobile, delay=120)

    def click_search(self) -> None:
        """Click the Search button and wait for results to load."""
        self.click_button(SEARCH_BUTTON_NAME)
        self.page.wait_for_load_state("networkidle")
        self.wait_for_idle(2)

    def select_patient_card(self, card_display_name: str) -> None:
        """Select an existing patient card from search results.

        Under parallel load (5 workers, multiple Aditya tests stacking on the
        same backend account), transient AntD toasts/loaders from the prior
        search action can cover the card and exhaust the 30 s wait. Wait for
        those overlays to dismiss, scroll the card into view, then click.
        """
        self.page.wait_for_load_state("networkidle")
        try:
            self.page.wait_for_selector(
                ".ant-modal-wrap, .ant-notification-notice, .ant-message-notice",
                state="hidden", timeout=8000,
            )
        except Exception:
            pass
        card = self.page.get_by_text(card_display_name, exact=False).first
        card.wait_for(state="visible", timeout=60000)
        try:
            card.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        card.click()
        self.wait_for_idle(2)

    def click_add_relative(self) -> None:
        """Click 'Add Relative' after search results."""
        self.click_text(ADD_RELATIVE_TEXT, exact=True)
        self.page.wait_for_load_state("networkidle")
        self.wait_for_idle(1)

    def select_relation(self, relation_name: str) -> None:
        """Open relation dropdown anchored on 'Relation with' label; pick option by exact content XPath."""
        label = self.page.locator("label").filter(has_text=RELATION_LABEL_CONTAINS).first
        label.wait_for(state="visible", timeout=8000)
        selector = label.locator(
            "xpath=following::div[contains(@class,'ant-select-selector')][1]"
        )
        selector.click(timeout=8000)
        self.wait_for_idle(1)
        option = self.page.locator(RELATION_OPTION_XPATH.format(relation_name))
        option.wait_for(state="visible", timeout=5000)
        option.click()
        self.wait_for_idle(2)

    def detect_error(self) -> Optional[str]:
        """Return visible AntD error text on the page, else None.

        Delegates to ``utils.error_detector.detect_ui_errors`` so we get the
        full 14-selector AntD/ARIA coverage (message bar, notification,
        modal, form validation, alert, role=alert, generic CSS patterns)
        instead of the previous 3-string substring match. The return shape
        (``str`` or ``None``) is preserved so existing call sites in
        ``flows/front_desk_flow.py`` continue working unchanged.
        """
        from utils.error_detector import detect_ui_errors
        err = detect_ui_errors(self.page)
        return err.text if err else None

    def select_salutation(self, value: str) -> None:
        """Open salutation dropdown via label-based XPath (avoids shifting AntD rc_select IDs)."""
        label = self.page.locator("label").filter(has_text=SALUTATION_LABEL_TEXT).first
        label.wait_for(state="visible", timeout=8000)
        selector = label.locator(
            "xpath=following::div[contains(@class,'ant-select-selector')][1]"
        )
        selector.click(timeout=8000)
        self.wait_for_idle(1)
        # AntD shows salutations with dot (Mr., Mrs.); Baby/Doctor have no dot
        display_value = value if value.endswith(".") else value + "."
        option = self.page.locator(SALUTATION_OPTION_XPATH.format(display_value))
        if option.count() == 0:
            option = self.page.locator(SALUTATION_OPTION_XPATH.format(value))
        option.click()
        self.wait_for_idle(2)

    def fill_patient_name(
        self, first: str, middle: str, last: str
    ) -> None:
        """Fill first, middle, and last name fields."""
        self.fill_textbox(FIRST_NAME_PLACEHOLDER, first)
        self.fill_textbox(MIDDLE_NAME_PLACEHOLDER, middle)
        self.fill_textbox(LAST_NAME_PLACEHOLDER, last)
        self.wait_for_idle(2)

    def select_gender(self, gender: str) -> None:
        """Click the gender button matching the given text."""
        self.page.get_by_role("button").filter(
            has_text=gender
        ).first.click()
        self.wait_for_idle(2)

    def fill_age(self, age: str) -> None:
        """Fill the age input field."""
        self.fill_placeholder(AGE_PLACEHOLDER, age)
        self.wait_for_idle(2)

    def fill_pin_code(self, pin: str) -> None:
        """Fill pincode and wait 3s for State/City/District auto-fill."""
        self.fill_textbox(PIN_CODE_PLACEHOLDER, pin)
        self.wait_for_idle(3)

    def fill_address(self, address: str) -> None:
        """Fill the address field."""
        self.fill_textbox(ADDRESS_PLACEHOLDER, address)
        self.wait_for_idle(2)

    def fill_email(self, email: str) -> None:
        """Fill the email field."""
        email_input = self.page.get_by_role(
            "textbox", name=EMAIL_PLACEHOLDER
        )
        email_input.wait_for(state="visible", timeout=5000)
        email_input.fill(email)
        self.wait_for_idle(1)

    def fill_mobile(self, mobile: str) -> None:
        """Fill the bottom mobile number field."""
        self.page.locator(MOBILE_INPUT).fill(mobile)
        self.wait_for_idle(2)

    def get_mobile_value(self) -> str:
        """Read the current value of the bottom mobile number field."""
        return self.get_input_value(MOBILE_INPUT)

    def fill_pin_code_if_empty(self, pin: str) -> None:
        """Fill pincode only if the field is currently empty."""
        field = self.page.get_by_role("textbox", name=PIN_CODE_PLACEHOLDER)
        if not field.input_value():
            field.fill(pin)
            self.wait_for_idle(3)

    def fill_address_if_empty(self, address: str) -> None:
        """Fill address only if the field is currently empty."""
        field = self.page.get_by_role("textbox", name=ADDRESS_PLACEHOLDER)
        if not field.input_value():
            field.fill(address)
            self.wait_for_idle(2)

    def fill_email_if_empty(self, email: str) -> None:
        """Fill email only if the field is currently empty."""
        field = self.page.get_by_role("textbox", name=EMAIL_PLACEHOLDER)
        field.wait_for(state="visible", timeout=5000)
        if not field.input_value():
            field.fill(email)
            self.wait_for_idle(1)

    def fill_mobile_if_empty(self, mobile: str) -> None:
        """Fill bottom mobile only if the field is currently empty."""
        field = self.page.locator(MOBILE_INPUT)
        if not field.input_value():
            field.fill(mobile)
            self.wait_for_idle(2)

    def add_test(self, test_name: str) -> None:
        """Search and select a test in the AntD combobox."""
        search_box = self.page.get_by_role(
            TEST_SEARCH_COMBOBOX_ROLE
        ).first
        search_box.click(force=True)
        self.wait_for_idle(0.4)
        search_box.press("Control+A")
        search_box.press("Backspace")
        self.wait_for_idle(0.3)
        search_box.type(_get_search_term(test_name), delay=80)
        self.wait_for_idle(1)
        search_box.press("Enter")
        self.wait_for_idle(1.2)

    def fill_payments(
        self, home_collection: str, cash: str, online: str
    ) -> None:
        """Fill the three payment amount fields using type()."""
        self.scroll_down(500)
        amounts = self.page.get_by_placeholder(PAYMENT_AMOUNT_PLACEHOLDER)
        self.scroll_to_element(amounts.nth(0))
        amounts.nth(0).type(home_collection)
        self.wait_for_idle(0.5)
        self.page.keyboard.press("Tab")
        self.wait_for_idle(1.5)
        amounts.nth(1).type(cash)
        self.wait_for_idle(1)
        amounts.nth(2).type(online)
        self.wait_for_idle(2)

    def get_balance(self) -> Optional[str]:
        """Read the auto-calculated balance from the disabled field."""
        return self.get_attribute_value(BALANCE_INPUT, "value")

    def click_print_bill(self) -> None:
        """Click Print Bill, capture the new tab, wait, and close it.

        Under parallel load the popup-page event can lag past the default
        30 s; retry up to 4 times with a 90 s window each. If no popup
        opens after the retries, raise — empirically, when the popup truly
        doesn't open the FD page state is left such that the next
        click_print_barcode also fails. Failing here surfaces the root
        cause cleanly instead of cascading.
        """
        btn = self.page.get_by_role("button", name=PRINT_BILL_BUTTON_NAME)
        btn.wait_for(state="visible", timeout=90000)
        # Visibility alone is insufficient — under load the modal may still
        # be wiring up its handlers when the button paints. Poll for enabled.
        enabled_deadline = time.time() + 10
        while not btn.is_enabled() and time.time() < enabled_deadline:
            self.wait_for_idle(0.3)
        context = self.page.context
        bill_page = None
        last_err: Optional[Exception] = None
        for attempt in range(4):
            try:
                with context.expect_page(timeout=90000) as new_page_info:
                    btn.click()
                bill_page = new_page_info.value
                break
            except Exception as e:
                last_err = e
                self.wait_for_idle(1)
                # If the modal was dismissed (button gone) re-locate so the
                # next attempt clicks the freshly-rendered button.
                try:
                    if not btn.is_visible():
                        btn = self.page.get_by_role(
                            "button", name=PRINT_BILL_BUTTON_NAME
                        )
                        btn.wait_for(state="visible", timeout=10000)
                except Exception:
                    pass
                continue
        if bill_page is None:
            raise TimeoutError(
                f"click_print_bill: popup tab did not open after 4 retries "
                f"(last error: {last_err})"
            )
        try:
            bill_page.wait_for_load_state()
        except Exception:
            pass
        try:
            bill_page.close()
        except Exception:
            pass

    def click_print_barcode(self) -> None:
        """Click Print Barcode and wait for the barcode modal to render.

        Under heavy parallel load the button can take longer than the 30 s
        default to render after the prior Print Bill step. Wait explicitly
        for visibility, then retry the click once if it doesn't take.
        """
        btn = self.page.get_by_role("button", name=PRINT_BARCODE_BUTTON_NAME)
        try:
            btn.wait_for(state="visible", timeout=60000)
        except Exception:
            pass
        last_err: Optional[Exception] = None
        for attempt in range(2):
            try:
                btn.click(timeout=30000)
                break
            except Exception as e:
                last_err = e
                self.wait_for_idle(2)
                continue
        else:
            raise TimeoutError(
                f"click_print_barcode: button click failed after 2 attempts "
                f"(last error: {last_err})"
            )
        self.page.wait_for_timeout(2000)

    def capture_samples(
        self, tests: List[Dict[str, str]]
    ) -> List[Dict[str, object]]:
        """Capture sample entries from the barcode modal using sample|sub_department match."""
        seen: set = set()
        pairs: List[tuple] = []
        for test in tests:
            key = (test["sample"], test["sub_department"])
            if key not in seen:
                pairs.append(key)
                seen.add(key)

        samples: List[Dict[str, object]] = []
        global_index = 0

        for sample_name, sub_dept in pairs:
            combo_text = f"{sample_name}{SAMPLE_SUB_DEPT_SEPARATOR}{sub_dept}"
            combo_labels = self.page.get_by_text(combo_text, exact=True)
            count = combo_labels.count()

            if count == 0:
                continue

            for i in range(count):
                label = combo_labels.nth(i)
                sample_id_el = label.locator(SAMPLE_ID_FOLLOWING_XPATH)
                raw_id = sample_id_el.inner_text().strip()
                # Strip "ID: " prefix from UI format like "ID: 698C0E2B4D7BC"
                sample_id = (
                    raw_id.replace("ID: ", "").strip() if raw_id.startswith("ID:") else raw_id
                )
                samples.append({
                    "name": sample_name,
                    "sub_department": sub_dept,
                    "id": sample_id,
                    "index": global_index,
                })
                global_index += 1

        return samples

    def close_barcode_modals(self) -> None:
        """Two-step modal close after sample capture.

        AntD modals usually transition to display:none rather than being
        removed from the DOM; wait for `state="hidden"` (not "detached")
        so the wait completes when the user-perceivable modal is gone.
        """
        first_modal_close = self.page.locator(FIRST_MODAL_CLOSE_XPATH)
        if first_modal_close.count() > 0:
            first_modal_close.first.click(force=True)
            self.page.wait_for_selector(
                FIRST_MODAL_SELECTOR, state="hidden", timeout=10000
            )
            self.wait_for_idle(4)

        final_modal_close = self.page.locator(FINAL_MODAL_CLOSE_SELECTOR)
        if final_modal_close.count() > 0:
            final_modal_close.click(force=True)
            self.page.wait_for_selector(
                FINAL_MODAL_SELECTOR, state="hidden", timeout=10000
            )
            self.wait_for_idle(4)

    def navigate_to_published_reports(self) -> None:
        """Expand Patients sidebar submenu and click Published Report."""
        patients = self.page.get_by_text("Patients", exact=True)
        patients.click()
        patients.hover()
        self.wait_for_idle(0.8)
        patients.click()
        self.wait_for_idle(1)
        self.page.get_by_text(PUBLISHED_REPORTS_SIDEBAR_TEXT, exact=True).click()
        self.wait_for_idle(2)

    def find_published_report(self, patient_name: str) -> Optional[Locator]:
        """Find a published report row by patient name."""
        rows = self.page.locator(PUBLISHED_REPORTS_TABLE_ROWS)
        try:
            rows.first.wait_for(state="visible", timeout=10000)
        except Exception:
            return None
        for i in range(rows.count()):
            row = rows.nth(i)
            if patient_name in row.inner_text():
                return row
        return None

    def view_report(self, row: Locator) -> bool:
        """Click View on a published report row."""
        btn = row.get_by_role("button", name=VIEW_REPORT_BUTTON_NAME)
        if btn.count() == 0:
            btn = row.get_by_role("button", name=DOWNLOAD_REPORT_BUTTON_NAME)
        if btn.count() == 0:
            return False
        btn.first.click()
        self.wait_for_idle(2)
        return True
