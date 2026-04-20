from playwright.sync_api import sync_playwright

# -------- CONFIG --------
BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

def login(page):
    page.goto(f"{BASE_URL}login")
    page.get_by_placeholder("Enter username").fill(USERNAME)
    page.get_by_placeholder("Enter password").fill(PASSWORD)
    page.get_by_role("button", name="Login").click()
    print("✅ Login successful")

def logout(page):
    # 1️⃣ Wait for profile image, then click
    page.get_by_role("img", name="profile").wait_for()
    page.get_by_role("img", name="profile").click()

    # 2️⃣ Click Log Out CTA
    page.get_by_role("heading", name="Log Out").click()

    # 3️⃣ Confirm logout
    page.get_by_text("Yes, Logout").click()

    print("🎉 Voila !!!")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    context = browser.new_context()
    page = context.new_page()

    # -------- LOGIN --------
    login(page)

    # -------- LOGOUT --------
    logout(page)
    page.wait_for_timeout(3000)

    browser.close()
