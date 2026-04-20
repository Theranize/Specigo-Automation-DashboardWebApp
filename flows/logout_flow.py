from pages.logout.logout_page import LogoutPage


def execute_logout(page):
    logout_page = LogoutPage(page)
    logout_page.logout()
