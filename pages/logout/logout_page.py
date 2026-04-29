from locators.logout.logout_locators import (
    PROFILE_ICON_NAME, LOGOUT_CTA_NAME, LOGOUT_CONFIRM_TEXT,
)

_PROFILE_ICON_PROBE_MS = 2000


class LogoutPage:
    def __init__(self, page):
        self.page = page

    def logout(self):
        try:
            if "/login" in (self.page.url or ""):
                return
        except Exception:
            pass

        icon = self.page.get_by_role("img", name=PROFILE_ICON_NAME)
        try:
            icon.wait_for(timeout=_PROFILE_ICON_PROBE_MS)
        except Exception:
            return
        icon.click()
        self.page.get_by_role("heading", name=LOGOUT_CTA_NAME).click()
        self.page.get_by_text(LOGOUT_CONFIRM_TEXT).click()
