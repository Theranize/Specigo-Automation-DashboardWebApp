from locators.logout.logout_locators import PROFILE_ICON_NAME, LOGOUT_CTA_NAME, LOGOUT_CONFIRM_TEXT


class LogoutPage:
    def __init__(self, page):
        self.page = page

    def logout(self):
        self.page.get_by_role("img", name=PROFILE_ICON_NAME).wait_for()
        self.page.get_by_role("img", name=PROFILE_ICON_NAME).click()
        self.page.get_by_role("heading", name=LOGOUT_CTA_NAME).click()
        self.page.get_by_text(LOGOUT_CONFIRM_TEXT).click()
