from playwright.sync_api import sync_playwright

BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "lab_tech1"
PASSWORD = "test@123"

FROM_DATE = "2026-02-03"
TO_DATE = "2026-02-03"

DEPARTMENT = "Pathology"
SUB_DEPARTMENT = "Hematology"

SEARCH_NAME = "Sunita"
SEARCH_MOBILE = "8839900148"

def login(page):
    page.goto(f"{BASE_URL}login")
    page.get_by_placeholder("Enter username").fill(USERNAME)
    page.get_by_placeholder("Enter password").fill(PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.get_by_text("Report Entry", exact=True).wait_for(state="visible")

def navigate_to_report_entry(page):
    page.get_by_text("Report Entry", exact=True).click()

def apply_date_filters(page):
    page.locator("input[type='date']").nth(0).fill(FROM_DATE)
    page.locator("input[type='date']").nth(1).fill(TO_DATE)

def select_department_and_subdept(page):
    page.locator("span").filter(has_text="None").nth(0).wait_for(state="visible")
    page.locator("span").filter(has_text="None").nth(0).hover()
    page.wait_for_timeout(1000)
    page.locator("span").filter(has_text="None").nth(0).click()
    page.wait_for_timeout(1000)
    page.get_by_text(DEPARTMENT, exact=True).click()
    page.wait_for_timeout(1000)

    page.locator("span").filter(has_text="None").nth(1).wait_for(state="visible")
    page.locator("span").filter(has_text="None").nth(1).click()
    page.wait_for_timeout(500)

    page.keyboard.type(SUB_DEPARTMENT[:3])
    page.wait_for_timeout(500)

    page.locator(
        f"div[title='{SUB_DEPARTMENT}'] div.ant-select-item-option-content"
    ).wait_for(state="visible")
    page.locator(
        f"div[title='{SUB_DEPARTMENT}'] div.ant-select-item-option-content"
    ).click()
    page.wait_for_timeout(1000)

def apply_search_filters(page):
    page.get_by_role("textbox", name="Search Here").nth(1).fill(SEARCH_NAME)
    page.get_by_role("textbox", name="Search Here").nth(2).fill(SEARCH_MOBILE)
    page.get_by_text("Apply Filter", exact=True).click()

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()
        login(page)
        navigate_to_report_entry(page)
        apply_date_filters(page)
        select_department_and_subdept(page)
        apply_search_filters(page)
        page.wait_for_timeout(3000)
        browser.close()

if __name__ == "__main__":
    run()
