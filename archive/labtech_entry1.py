from playwright.sync_api import sync_playwright
import json

BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "lab_tech1"
PASSWORD = "test@123"

FROM_DATE = "2026-02-05"
TO_DATE = "2026-02-05"

SEARCH_NAME = "Amit"
SEARCH_MOBILE = "8839900148"

JSON_PATH = "data/test_results.json"


def load_test_data():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["tests"]


def login(page):
    page.goto(f"{BASE_URL}login")
    page.get_by_placeholder("Enter username").fill(USERNAME)
    page.get_by_placeholder("Enter password").fill(PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.get_by_text("Report Entry", exact=True).wait_for(state="visible")


def navigate_to_report_entry(page):
    page.get_by_text("Report Entry", exact=True).click()


def apply_date_and_search(page):
    page.locator("input[type='date']").nth(0).fill(FROM_DATE)
    page.locator("input[type='date']").nth(1).fill(TO_DATE)

    page.get_by_role("textbox", name="Search Here").nth(1).fill(SEARCH_NAME)
    page.wait_for_timeout(300)
    page.get_by_role("textbox", name="Search Here").nth(2).fill(SEARCH_MOBILE)
    page.wait_for_timeout(300)

    page.get_by_text("Apply Filter", exact=True).click()
    page.wait_for_timeout(3000)


def open_report(page):
    rows = page.locator("tr.ant-table-row")
    rows.first.wait_for(state="visible")

    for _ in range(10):
        rows.first.hover()
        page.wait_for_timeout(300)

        icon = rows.first.locator("img[alt='Report Entry']")
        if icon.count() > 0:
            icon.first.click()
            page.wait_for_timeout(3000)
            return

        page.mouse.wheel(0, 400)
        page.wait_for_timeout(400)

    raise Exception("Report Entry icon not found")


# ---------------- SUB-DEPARTMENT NAVIGATION ---------------- #

def reset_to_first_sub_dept(page):
    prev_btn = page.get_by_role("button", name="Previous Sub-Department")
    while prev_btn.is_enabled():
        prev_btn.click()
        page.wait_for_timeout(1200)


def scroll_until_test_visible(page, test_name, max_scrolls=8):
    locator = page.locator(f'h1:has-text("{test_name}")')
    for _ in range(max_scrolls):
        if locator.count() > 0:
            return locator.first
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(400)
    return None


def find_test_row_on_current_page(page, test_name):
    heading = scroll_until_test_visible(page, test_name)
    if not heading:
        return None

    row = heading.locator("xpath=ancestor::tr")
    if row.count() == 0:
        return None

    row.first.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    return row.first


def traverse_sub_depts_for_test(page, test_name):
    """
    Always:
    1. Reset to first sub-dept
    2. Scan forward using Next
    3. Visit each sub-dept once
    """
    reset_to_first_sub_dept(page)

    next_btn = page.get_by_role("button", name="Next Sub-Department")

    while True:
        row = find_test_row_on_current_page(page, test_name)
        if row:
            print(f"A worked | {test_name}")
            return row

        if next_btn.is_enabled():
            next_btn.click()
            page.wait_for_timeout(1500)
        else:
            break

    print(f"FAILED | {test_name} | not found in any sub-department")
    return None


# ---------------- PARAMETER / RESAMPLE / SAVE ---------------- #

def fill_parameters(page, row, test_name, parameters):
    for param, value in parameters.items():
        label = row.get_by_text(param, exact=True)
        if label.count() == 0:
            print(f"FAILED | {test_name} | parameter not found → {param}")
            return False

        container = label.locator(
            "xpath=ancestor::div[contains(@class,'flex')][1]"
        )
        textbox = container.locator("input[type='text']")

        if textbox.count() == 0 or textbox.first.is_disabled():
            print(f"FAILED | {test_name} | input disabled → {param}")
            return False

        textbox.first.fill(str(value))
        page.wait_for_timeout(200)

    print(f"C worked | {test_name}")
    return True


def handle_resample(page, row, reason):
    btn = row.get_by_role("button", name="Re-sample")
    if btn.count() == 0:
        print("FAILED | resample button not found")
        return False

    btn.first.click()
    page.wait_for_timeout(1500)

    option = page.locator(f"//span[contains(text(),'{reason}')]")
    if option.count() > 0:
        option.first.click()
    else:
        page.get_by_role("textbox").fill(reason)

    page.get_by_role("button", name="Add & Submit").click()
    page.wait_for_timeout(2000)

    print("RESAMPLE worked")
    return True


def save_test(page, row, test_name):
    save_btn = row.get_by_role("button", name="Save")

    if save_btn.count() == 0 or save_btn.first.is_disabled():
        print(f"FAILED | {test_name} | save disabled")
        return False

    save_btn.first.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    save_btn.first.click()
    page.wait_for_timeout(1000)

    yes_btn = page.get_by_role("button", name="Yes")
    if yes_btn.count() > 0:
        yes_btn.first.click()
        page.wait_for_timeout(2000)

    print(f"SAVE worked | {test_name}")
    return True


# ---------------- MAIN ---------------- #

def run():
    tests = load_test_data()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=40)
        page = browser.new_page()

        login(page)
        navigate_to_report_entry(page)
        apply_date_and_search(page)
        open_report(page)

        for test in tests:
            test_name = test["test_name"]
            parameters = test.get("parameters", {})
            resample = test.get("resample", False)
            reason = test.get("resample_reason", "")

            print(f"\n🔍 Processing test: {test_name}")

            row = traverse_sub_depts_for_test(page, test_name)
            if not row:
                continue

            if resample:
                handle_resample(page, row, reason)
                continue

            if fill_parameters(page, row, test_name, parameters):
                save_test(page, row, test_name)

        page.wait_for_timeout(5000)
        browser.close()


if __name__ == "__main__":
    run()
