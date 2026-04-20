from playwright.sync_api import sync_playwright

# -------- CONFIG --------
BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

# -------- INPUT --------
PATIENT_MOBILE = "9123456789"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_page()

    # ================= LOGIN =================
    page.goto(f"{BASE_URL}login")
    page.fill("input[placeholder='Enter username']", USERNAME)
    page.fill("input[placeholder='Enter password']", PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")

    # ================= ADD PATIENT =================
    page.get_by_role("button", name="Add Patient").click()

    # ================= PHONE NUMBER =================
    phone_input = page.locator(
        "input[placeholder='Enter Phone Number'][type='number']"
    ).nth(0)

    phone_input.wait_for(state="visible", timeout=10000)
    phone_input.click()
    phone_input.press("Control+A")
    phone_input.press("Backspace")
    phone_input.type(PATIENT_MOBILE, delay=120)

    # ================= SEARCH =================
    page.get_by_role("button", name="Search").click()

    print("✅ Search completed")

    # ================= ADD RELATIVE (LOCATOR ONLY USED HERE) =================
    add_relative_btn = page.get_by_text("Add Relative", exact=True)
    add_relative_btn.wait_for(state="visible", timeout=5000)
    add_relative_btn.click()

    print("✅ Add Relative clicked")

    # ================= END =================
    page.wait_for_timeout(5000)
    browser.close()
