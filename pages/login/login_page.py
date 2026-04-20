from locators.login.login_locators import USERNAME_INPUT, PASSWORD_INPUT, LOGIN_BUTTON_NAME


class LoginPage:
    def __init__(self, page):
        self.page = page

    def login(self, username, password):
        self.page.locator(USERNAME_INPUT).fill(username)
        self.page.locator(PASSWORD_INPUT).fill(password)
        self.page.get_by_role("button", name=LOGIN_BUTTON_NAME).click()
        self.page.wait_for_url(lambda url: "/login" not in url, timeout=120000)
