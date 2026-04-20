from pages.login.login_page import LoginPage


def execute_login(page, role, credentials):
    login_page = LoginPage(page)
    login_page.login(credentials["username"], credentials["password"])
