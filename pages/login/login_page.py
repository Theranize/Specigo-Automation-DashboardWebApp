from locators.login.login_locators import USERNAME_INPUT, PASSWORD_INPUT, LOGIN_BUTTON_NAME


class LoginPage:
    def __init__(self, page):
        self.page = page

    def login(self, username, password):
        # Defensive: under heavy parallel load, a prior logout may not have
        # finished navigating back to /login when this is called mid-test.
        # If we're not at /login, navigate there explicitly.
        try:
            current = self.page.url or ""
        except Exception:
            current = ""
        if "/login" not in current:
            base = getattr(self.page.context, "base_url", "") or ""
            try:
                self.page.goto(base + "login")
            except Exception:
                pass
        user_input = self.page.locator(USERNAME_INPUT)
        user_input.wait_for(state="visible", timeout=60000)
        user_input.fill(username)
        self.page.locator(PASSWORD_INPUT).fill(password)
        self.page.get_by_role("button", name=LOGIN_BUTTON_NAME).click()
        self.page.wait_for_url(lambda url: "/login" not in url, timeout=120000)
