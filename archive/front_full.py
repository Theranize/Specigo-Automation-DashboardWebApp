from playwright.sync_api import sync_playwright
import time

# -------- CONFIG --------
BASE_URL = "https://frontenddevh1.theranize.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

# -------- PATIENT DATA --------
SALUTATION = "Mr."
FIRST_NAME = "Arun"
MIDDLE_NAME = "Kumar"
LAST_NAME = "Sharma"
GENDER = "Male"
AGE = "32"
PIN_CODE = "492001"
ADDRESS = "Shankar Nagar, Raipur"
MOBILE = "8123456789"
RISK_LEVEL = "High Risk"

# -------- TESTS --------
TESTS = [
    "Complete Blood Count (CBC) A",
    "24 Hrs Urinary Potassium",
    "Arterial Blood Gas (ABG)"
]


def get_search_term(test_name: str) -> str:
    """Use first two words for AntD search stability"""
    return " ".join(test_name.split()[:2])


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # ================= LOGIN =================
    page.goto(f"{BASE_URL}login")
    page.fill("input[placeholder='Enter username']", USERNAME)
    page.fill("input[placeholder='Enter password']", PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.wait_for_url("**/")
    time.sleep(2)

    # ================= ADD PATIENT =================
    page.click('button:has-text("Add Patient")')
    page.wait_for_url("**/geninfo")
    time.sleep(2)

    # ================= CONDITIONAL RISK =================
    page.get_by_text(RISK_LEVEL, exact=False).click()
    time.sleep(2)

    # ================= SALUTATION =================
    page.locator("#rc_select_1").first.click()
    page.locator(
        f"//div[@class='ant-select-item-option-content'][normalize-space()='{SALUTATION}']"
    ).click()
    time.sleep(2)

    # ================= NAME =================
    page.get_by_role("textbox", name="Enter First Name").fill(FIRST_NAME)
    page.get_by_role("textbox", name="Enter Middle Name").fill(MIDDLE_NAME)
    page.get_by_role("textbox", name="Enter Last Name").fill(LAST_NAME)
    time.sleep(2)

    # ================= GENDER =================
    page.get_by_role("button").filter(has_text=GENDER).first.click()
    time.sleep(2)

    # ================= AGE =================
    page.get_by_placeholder("Enter Age").fill(AGE)
    time.sleep(2)

    # ================= PIN CODE =================
    page.get_by_role("textbox", name="Enter Pin code").fill(PIN_CODE)
    time.sleep(2)

    # ================= ADDRESS =================
    page.get_by_role("textbox", name="Enter Address Here").fill(ADDRESS)
    time.sleep(2)

    # ================= MOBILE =================
    page.locator('input[name="mobile"]').fill(MOBILE)
    time.sleep(2)

    # ================= NEXT =================
    page.get_by_role("button", name="Next").click()
    time.sleep(3)

    # ================= ADD TESTS =================
    search_box = page.get_by_role("combobox").first

    for test in TESTS:
        search_box.click()
        time.sleep(0.5)

        search_box.press("Control+A")
        search_box.press("Backspace")
        time.sleep(0.5)

        search_box.type(get_search_term(test), delay=80)
        time.sleep(1)

        search_box.press("Enter")
        time.sleep(1.5)

    # ================= PAYMENTS =================
    # Home Collection
    page.get_by_placeholder("Enter Amount").nth(0).type("500")
    time.sleep(1)

     # Cash
    page.get_by_placeholder("Enter Amount").nth(1).type("1500")
    time.sleep(1)

    # Online
    page.get_by_placeholder("Enter Amount").nth(2).type("800")
    time.sleep(2)

    # ================= READ BALANCE (CORRECT WAY) =================
    balance_input = page.locator(
        "input[type='number'][disabled][readonly]"
    ).nth(0)

    balance_input.wait_for(state="visible", timeout=5000)
    balance_value = balance_input.get_attribute("value")

    print("BALANCE AMOUNT:", balance_value)

    # ---------------- SUBMIT ----------------
    submit_btn = page.get_by_role("button", name="Submit")
    submit_btn.wait_for(state="visible", timeout=5000)
    submit_btn.click()

    # wait for submission processing
    time.sleep(3)


    # ================= END =================
    time.sleep(5)
    print("success front end")
    browser.close()
