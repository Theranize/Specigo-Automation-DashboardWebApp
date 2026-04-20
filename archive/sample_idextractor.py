from playwright.sync_api import sync_playwright

BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

SALUTATION = "Mr."
FIRST_NAME = "Arun"
MIDDLE_NAME = "Kumar"
LAST_NAME = "Sharma"
GENDER = "Male"
AGE = "32"
PIN_CODE = "492001"
ADDRESS = "Shankar Nagar, Raipur"
MOBILE = "8924457749"
RISK_LEVEL = "High Risk"

TESTS = [
    "Complete Blood Count (CBC) A",
    "24 Hrs Urinary Potassium",
    "Arterial Blood Gas (ABG)",
    "Acid Phosphatase Total, Serum"
]

SAMPLES = [
    "24-hour urine",
    "Whole Blood/Plasma",
    "Blood"
]

def get_search_term(test_name: str) -> str:
    return " ".join(test_name.split()[:2])

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(f"{BASE_URL}login")
    page.fill("input[placeholder='Enter username']", USERNAME)
    page.fill("input[placeholder='Enter password']", PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.wait_for_url("**/")
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Add Patient").click()
    page.wait_for_url("**/geninfo")

    page.get_by_text(RISK_LEVEL, exact=False).click()

    page.locator("#rc_select_1").first.click()
    page.locator(
        f"//div[@class='ant-select-item-option-content'][normalize-space()='{SALUTATION}']"
    ).click()

    page.get_by_role("textbox", name="Enter First Name").fill(FIRST_NAME)
    page.get_by_role("textbox", name="Enter Middle Name").fill(MIDDLE_NAME)
    page.get_by_role("textbox", name="Enter Last Name").fill(LAST_NAME)

    page.get_by_role("button").filter(has_text=GENDER).first.click()

    page.get_by_placeholder("Enter Age").fill(AGE)
    page.get_by_role("textbox", name="Enter Pin code").fill(PIN_CODE)
    page.get_by_role("textbox", name="Enter Address Here").fill(ADDRESS)
    page.locator('input[name="mobile"]').fill(MOBILE)

    page.wait_for_timeout(4000)
    page.get_by_role("button", name="Next").click()
    page.wait_for_load_state("networkidle")

    search_box = page.get_by_role("combobox").first

    for test in TESTS:
        search_box.click()
        search_box.press("Control+A")
        search_box.press("Backspace")
        search_box.type(get_search_term(test), delay=80)
        page.wait_for_timeout(800)
        search_box.press("Enter")
        page.wait_for_timeout(800)

    page.get_by_placeholder("Enter Amount").nth(0).type("500")
    page.get_by_placeholder("Enter Amount").nth(1).type("1500")
    page.get_by_placeholder("Enter Amount").nth(2).type("800")

    balance_input = page.locator("input[type='number'][disabled][readonly]").nth(0)
    balance_input.wait_for(state="visible", timeout=5000)
    balance_value = balance_input.get_attribute("value")
    print("BALANCE AMOUNT:", balance_value)

    page.get_by_role("button", name="Submit").click()
    page.wait_for_load_state("networkidle")

    with context.expect_page() as new_page_info:
        page.get_by_role("button", name="Print Bill").click()
    bill_page = new_page_info.value
    bill_page.wait_for_load_state()
    bill_page.close()

    page.get_by_role("button", name="Print Barcode").click()
    page.wait_for_timeout(2000)

    for sample in SAMPLES:
        sample_labels = page.get_by_text(f"{sample} -", exact=True)
        count = sample_labels.count()

        if count == 0:
            continue

        for i in range(count):
            label = sample_labels.nth(i)
            sample_id_element = label.locator("xpath=following::div[1]")
            sample_id = sample_id_element.inner_text().strip()
            print(f"[{i+1}] {sample} - {sample_id}")

    first_modal_close = page.locator("//div[@class='ant-modal css-q13irl']//div//button[@aria-label='Close']")
    if first_modal_close.count() > 0:
        first_modal_close.first.click(force=True)
        page.wait_for_selector("//div[@class='ant-modal css-q13irl']", state="detached", timeout=10000)
        page.wait_for_timeout(4000)

    final_modal_close = page.locator("div.ant-modal.print-modal span[aria-label='close']")
    if final_modal_close.count() > 0:
        final_modal_close.click(force=True)
        page.wait_for_selector("div.ant-modal.print-modal", state="detached", timeout=10000)
        page.wait_for_timeout(4000)

    browser.close()
