"""Base page object with reusable UI utility methods."""

import time
from typing import Optional
from playwright.sync_api import Page, Locator


class BasePage:
    """Base class for all page objects."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def wait_for_navigation(self, url_pattern: str, timeout: int = 30000) -> None:
        """Wait until the URL matches the given glob pattern."""
        self.page.wait_for_url(url_pattern, timeout=timeout)

    def wait_for_idle(self, seconds: float = 2.0) -> None:
        """Explicit wait for UI to settle after an action."""
        time.sleep(seconds)

    def scroll_down(self, pixels: int = 500) -> None:
        """Scroll the page down by the given pixel amount."""
        self.page.mouse.wheel(0, pixels)
        time.sleep(0.5)

    def scroll_to_element(self, locator: Locator) -> None:
        """Scroll an element into the viewport before interacting."""
        locator.scroll_into_view_if_needed()
        time.sleep(0.5)

    def click_button(self, name: str, scroll: bool = False) -> None:
        """Click a button identified by its accessible name."""
        btn = self.page.get_by_role("button", name=name)
        if scroll:
            self.scroll_to_element(btn)
        btn.click()

    def click_text(self, text: str, exact: bool = True) -> None:
        """Click an element by its visible text content."""
        el = self.page.get_by_text(text, exact=exact)
        el.wait_for(state="visible", timeout=5000)
        el.click()

    def fill_textbox(self, name: str, value: str) -> None:
        """Fill a textbox identified by its accessible name."""
        self.page.get_by_role("textbox", name=name).fill(value)

    def fill_placeholder(self, placeholder: str, value: str) -> None:
        """Fill an input identified by its placeholder text."""
        self.page.get_by_placeholder(placeholder).fill(value)

    def type_into(self, locator: Locator, value: str, delay: int = 0) -> None:
        """Type into a locator character by character (for AntD inputs)."""
        locator.type(value, delay=delay)

    def select_antd_option(
        self, dropdown_selector: str, option_xpath: str
    ) -> None:
        """Open an AntD dropdown and click the option matching the XPath."""
        self.page.locator(dropdown_selector).first.click()
        self.wait_for_idle(1.0)
        self.page.locator(option_xpath).click()

    def get_attribute_value(
        self, selector: str, attribute: str, nth: int = 0
    ) -> Optional[str]:
        """Read an attribute value from a matched element."""
        el = self.page.locator(selector).nth(nth)
        el.wait_for(state="visible", timeout=5000)
        return el.get_attribute(attribute)

    def get_input_value(self, selector: str) -> str:
        """Read the current value of an input element."""
        return self.page.locator(selector).input_value()
