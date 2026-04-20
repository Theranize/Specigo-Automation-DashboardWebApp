from playwright.sync_api import sync_playwright
import random

BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "lab_tech1"
PASSWORD = "test@123"

FROM_DATE = "2026-02-03"
TO_DATE = "2026-02-03"

DEPARTMENT = "Biochemistry"
SUB_DEPARTMENT = "Clinical Chemistry"

SEARCH_NAME = "Sunita"
SEARCH_MOBILE = "8839900148"

CHECKBOX_PICK_COUNT = 2

SAMPLES_TO_MATCH = [
    {"sample": "Whole Blood", "id": "698197967870E", "action": "Refresh"},
    {
        "sample": "Urine",
        "id": "6981993EBC1AA",
        "action": "Reject",
        "sub_dept2": "Clinical Pathology",
        "rejection_reason": "Sample integrity issue",
    },
    {"sample": "24-hour urine", "id": "69818563151F0", "action": "Accept"},
    {
        "sample": "Whole Blood",
        "id": "698179FF45529",
        "action": "Reject",
        "sub_dept2": "Haematology",
        "rejection_reason": "Clotted sample",
    },
    {"sample": "Whole Blood", "id": "6981856315612", "action": "Accept"},
]

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
    page.locator("span").filter(has_text="None").nth(0).click()
    page.get_by_text(DEPARTMENT, exact=True).click()
    page.wait_for_timeout(500)

    page.locator("span").filter(has_text="None").nth(1).click()
    page.wait_for_timeout(300)

    page.keyboard.type(SUB_DEPARTMENT[:3])
    page.wait_for_timeout(300)

    page.locator(
        f"div[title='{SUB_DEPARTMENT}'] div.ant-select-item-option-content"
    ).click()
    page.wait_for_timeout(500)

def apply_search_filters(page):
    page.get_by_role("textbox", name="Search Here").nth(1).fill(SEARCH_NAME)
    page.get_by_role("textbox", name="Search Here").nth(2).fill(SEARCH_MOBILE)
    page.get_by_text("Apply Filter", exact=True).click()

def handle_rejection(page, sub_row, config):
    sub_row.locator("span").filter(has_text="Reject").click()
    page.wait_for_timeout(800)

    modal = page.locator("div.ant-modal-body")
    modal.wait_for(state="visible")

    action_done = False

    if "sub_dept2" in config and modal.locator(
        f':text-is("{config["sub_dept2"]}")'
    ).count() > 0:

        modal.locator(f':text-is("{config["sub_dept2"]}")').click()
        page.wait_for_timeout(500)

        checkboxes = modal.get_by_role("checkbox")
        total = checkboxes.count()

        if total > 0:
            pick = min(CHECKBOX_PICK_COUNT, total)
            picks = random.sample(range(total), k=pick)
            for i in picks:
                checkboxes.nth(i).check()
            action_done = True

    if not action_done:
        modal.get_by_role("textbox").fill(
            config.get("rejection_reason", "Rejected")
        )
        action_done = True

    if action_done:
        modal.get_by_role("button", name="Send").click()
        print(f"{config['sample']} | {config['id']} | Reject")

    page.wait_for_timeout(800)

def parse_rows_and_perform_actions(page):
    page.locator("tr.ant-table-row").first.wait_for(state="visible")
    rows = page.locator("tr.ant-table-row")

    for i in range(rows.count()):
        row = rows.nth(i)
        sub_rows = row.locator("div.ant-row")

        for j in range(sub_rows.count()):
            sub_row = sub_rows.nth(j)
            text = sub_row.inner_text()

            for item in SAMPLES_TO_MATCH:
                if item["sample"] in text and item["id"] in text:
                    if item["action"] == "Accept":
                        sub_row.locator("span").filter(has_text="Accept").click()
                        print(f"{item['sample']} | {item['id']} | Accept")
                        page.wait_for_timeout(500)
                    elif item["action"] == "Refresh":
                        sub_row.locator("span").filter(has_text="Refresh").click()
                        print(f"{item['sample']} | {item['id']} | Refresh")
                        page.wait_for_timeout(500)
                    elif item["action"] == "Reject":
                        handle_rejection(page, sub_row, item)

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        page = browser.new_page()

        login(page)
        navigate_to_report_entry(page)
        apply_date_filters(page)
        select_department_and_subdept(page)
        apply_search_filters(page)
        parse_rows_and_perform_actions(page)

        page.wait_for_timeout(3000)
        browser.close()

if __name__ == "__main__":
    run()
