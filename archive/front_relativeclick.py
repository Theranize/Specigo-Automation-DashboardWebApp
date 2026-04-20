from playwright.sync_api import sync_playwright

BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

PATIENT_MOBILE = "8839900148"
PATIENT_NAME_OPTION = "Arun Kumar"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_page()

    page.goto(f"{BASE_URL}login")
    page.fill("input[placeholder='Enter username']", USERNAME)
    page.fill("input[placeholder='Enter password']", PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="Add Patient").click()

    phone_input = page.locator(
        "input[placeholder='Enter Phone Number'][type='number']"
    ).nth(0)

    phone_input.wait_for(state="visible", timeout=10000)
    phone_input.click()
    phone_input.press("Control+A")
    phone_input.press("Backspace")
    phone_input.type(PATIENT_MOBILE, delay=120)

    page.get_by_role("button", name="Search").click()

    patient_option = page.locator("div").filter(has_text=PATIENT_NAME_OPTION).first
    patient_option.wait_for(state="visible", timeout=10000)
    patient_option.click()

    page.wait_for_timeout(4000)
    page.get_by_role("button", name="Next").click()
    page.wait_for_load_state("networkidle")

    page.wait_for_timeout(5000)
    browser.close()
