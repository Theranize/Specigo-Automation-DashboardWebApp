from playwright.sync_api import sync_playwright

# -------- CONFIG --------
BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

# -------- GLOBAL INPUTS --------
PATIENT_MOBILE = "9123456789"
RELATION_NAME = "Mother"
EMAIL_ID = "testuser@example.com"

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

    # ================= MOBILE SEARCH =================
    mobile_input = page.locator(
        "input[placeholder='Enter Phone Number'][type='number']"
    ).first
    mobile_input.wait_for(state="visible", timeout=10000)
    mobile_input.type(PATIENT_MOBILE, delay=120)

    page.get_by_role("button", name="Search").click()

    # ================= ADD RELATIVE =================
    page.get_by_text("Add Relative", exact=True).click()

    # ================= OPEN RELATION DROPDOWN =================
    relation_dropdown = page.locator("#rc_select_6").first
    relation_dropdown.wait_for(state="visible", timeout=5000)
    relation_dropdown.click()

    # ================= SELECT RELATION =================
    relation_option = page.get_by_text(RELATION_NAME, exact=True)
    relation_option.wait_for(state="visible", timeout=3000)
    relation_option.click()
    print(f"✅ Relation selected: {RELATION_NAME}")

    # ================= EMAIL INPUT =================
    email_input = page.get_by_role("textbox", name="Enter Email")
    email_input.wait_for(state="visible", timeout=5000)
    email_input.fill(EMAIL_ID)
    print(f"✅ Email entered: {EMAIL_ID}")

    # ================= SCROLL =================
    page.mouse.wheel(0, 800)

    
    # ================= VISUAL CONFIRMATION WAIT =================
    page.wait_for_timeout(3000)
    print("Viola !!!")

    # ================= END =================
    browser.close()
