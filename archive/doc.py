from playwright.sync_api import sync_playwright
import json
import time

BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "testdoc"
PASSWORD = "test@123"

FROM_DATE = "2026-02-05"
TO_DATE = "2026-02-05"

SEARCH_NAME = "Amit"
SEARCH_MOBILE = "8839900148"

JSON_PATH = "data/doc_test.json"


def load_test_data():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["sub_departments"]


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
    time.sleep(0.3)
    page.get_by_role("textbox", name="Search Here").nth(2).fill(SEARCH_MOBILE)
    time.sleep(0.3)
    page.get_by_text("Apply Filter", exact=True).click()
    time.sleep(3)


def open_report(page):
    rows = page.locator("tr.ant-table-row")
    rows.first.wait_for(state="visible")
    rows.first.hover()
    page.locator("img[alt='Report Entry']").first.click()
    time.sleep(3)


def is_sub_dept_visible(page, sub_dept):
    return page.get_by_role("heading", name=sub_dept).count() > 0


def move_to_sub_dept(page, sub_dept):
    for _ in range(20):
        if is_sub_dept_visible(page, sub_dept):
            return True
        next_btn = page.get_by_role("button", name="Next Sub-Department")
        prev_btn = page.get_by_role("button", name="Previous Sub-Department")
        if next_btn.is_enabled():
            next_btn.click()
        elif prev_btn.is_enabled():
            prev_btn.click()
        time.sleep(1.5)
    return False


def find_test_row(page, test_name, max_scrolls=10):
    for _ in range(max_scrolls):
        heading = page.locator(f"h1:has-text('{test_name}')")
        if heading.count() > 0:
            row = heading.first.locator("xpath=ancestor::tr")
            if row.count() > 0:
                row.first.scroll_into_view_if_needed()
                time.sleep(0.3)
                return row.first
        page.mouse.wheel(0, 400)
        time.sleep(0.4)
    return None


def fill_parameters(row, parameters):
    for param, value in parameters.items():
        label = row.get_by_text(param, exact=True)
        container = label.locator("xpath=ancestor::div[contains(@class,'flex')][1]")
        textbox = container.locator("input[type='text']")
        textbox.first.fill(str(value))
        time.sleep(0.3)


def handle_resample(page, row, reason):
    row.locator("button").filter(has_text="Re-sample").click()
    dialog = page.get_by_role("dialog")
    dialog.wait_for(state="visible")

    checkbox = dialog.get_by_label(reason)
    if checkbox.count() > 0:
        checkbox.first.check()
    else:
        dialog.get_by_role("textbox").first.fill(reason)

    dialog.get_by_role("button", name="Add & Submit").click()
    time.sleep(1.5)


def handle_retest(page, row):
    row.get_by_role("button", name="Re-Test").click()
    page.get_by_role("button", name="Yes").wait_for(state="visible")
    page.get_by_role("button", name="Yes").click()
    time.sleep(1.5)


def wait_until_enabled(button, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        if button.is_enabled():
            return
        time.sleep(0.3)
    raise Exception("Button did not become enabled")


def save(page, row):
    btn = row.get_by_role("button", name="Save")
    btn.wait_for(state="visible")
    wait_until_enabled(btn)
    btn.click()
    page.get_by_role("button", name="Yes").wait_for(state="visible")
    page.get_by_role("button", name="Yes").click()
    time.sleep(1.5)


def approve(page, row, final_action):
    btn = row.get_by_role("button", name="Approve")
    btn.wait_for(state="visible")
    wait_until_enabled(btn)
    btn.click()

    dialog = page.get_by_role("dialog")
    dialog.wait_for(state="visible")

    if final_action == "partial_approve":
        dialog.get_by_role("button", name="Partially Approve").click()
    else:
        dialog.get_by_role("button", name="Fully Approve").click()

    time.sleep(1.5)


def rectify(page, row, rectification):
    btn = row.get_by_role("button", name="Rectify")
    btn.wait_for(state="visible")
    wait_until_enabled(btn)
    btn.click()

    dialog = page.get_by_role("dialog")
    dialog.wait_for(state="visible")

    dialog.get_by_text(rectification["reason"], exact=True).click()

    if rectification["reason"] == "Others":
        time.sleep(1)
        dialog.get_by_role("textbox", name="Enter The Reason").fill(rectification["other_text"])

    dialog.locator('span:has-text("Submit")').click()

    page.get_by_role("button", name="Yes").wait_for(state="visible")
    page.get_by_role("button", name="Yes").click()

    time.sleep(2)


def run():
    data = load_test_data()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=40)
        page = browser.new_page()

        login(page)
        navigate_to_report_entry(page)
        apply_date_and_search(page)
        open_report(page)

        for sub in data:
            if not move_to_sub_dept(page, sub["sub_dept_name"]):
                continue

            for test in sub["tests"]:
                row = find_test_row(page, test["test_name"])
                if not row:
                    continue

                independent = test.get("independent_action")
                final_action = test.get("final_action")
                parameters = test.get("parameters", {})
                rectification = test.get("rectification")

                if independent:
                    if independent["type"] == "retest":
                        handle_retest(page, row)
                    elif independent["type"] == "resample":
                        handle_resample(page, row, independent["reason"])
                    continue

                if parameters:
                    fill_parameters(row, parameters)

                if final_action == "rectify":
                    rectify(page, row, rectification)
                    continue

                if parameters:
                    save(page, row)

                if final_action:
                    approve(page, row, final_action)

        time.sleep(5)
        browser.close()


if __name__ == "__main__":
    run()
