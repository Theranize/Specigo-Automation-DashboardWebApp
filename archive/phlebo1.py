from playwright.sync_api import sync_playwright

# ================= CONFIG =================
BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

# ================= FILTERS =================
FROM_DATE = "28/01/2026"
TO_DATE   = "28/01/2026"

SEARCH_NAME = "Arun Kumar"
SEARCH_MOBILE = "8423456789"

# ================= SAMPLE NAME → ID MAP =================
SAMPLE_NAME_ID_MAP = {
    
    "Serum": "6979D070D88C5",
    "Whole Blood/Plasma": "6979D070D7993"
}


# ================= CORE LOGIC =================
def toggle_sample_across_rows(page, sample_name, sample_id):
    """
    Searches from row 1 to N.
    Inside each row, searches sample blocks.
    Toggles ONLY when sample_name + sample_id
    exist in the SAME block text.
    """

    print(f"\n🔍 Looking for sample: {sample_name} | {sample_id}")

    rows = page.locator("tbody tr")
    row_count = rows.count()

    for row_index in range(row_count):
        row = rows.nth(row_index)

        sample_blocks = row.locator(
            "div.self-stretch.inline-flex.justify-between.items-center.gap-1"
        )
        block_count = sample_blocks.count()

        for block_index in range(block_count):
            block = sample_blocks.nth(block_index)

            # 🔒 STRICT TEXT MATCH (FIX)
            block_text = block.inner_text()

            if sample_name in block_text and sample_id in block_text:
                toggle = block.locator("button.ant-switch")
                toggle.wait_for(state="visible", timeout=3000)

                if toggle.get_attribute("aria-checked") != "true":
                    toggle.click()
                    print(
                        f"✅ TOGGLED → Row {row_index + 1}, "
                        f"Block {block_index + 1} "
                        f"({sample_name})"
                    )
                else:
                    print(
                        f"ℹ️ Already ON → Row {row_index + 1}, "
                        f"Block {block_index + 1} "
                        f"({sample_name})"
                    )

                return  # ✅ stop after correct match

    raise Exception(
        f"❌ Sample not found: {sample_name} | {sample_id}"
    )


# ================= MAIN FLOW =================
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_page()

    # ---------- LOGIN ----------
    page.goto(f"{BASE_URL}login")
    page.fill("input[placeholder='Enter username']", USERNAME)
    page.fill("input[placeholder='Enter password']", PASSWORD)
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")
    print("✅ Logged in")

    # ---------- NAVIGATION ----------
    phlebo = page.get_by_text("Phlebotomists", exact=True)
    phlebo.wait_for(state="visible", timeout=5000)
    phlebo.click()
    phlebo.hover()
    page.wait_for_timeout(600)
    phlebo.click()

    page.get_by_text("Sample Tracker", exact=True).click()

    # ---------- PAGE VERIFY ----------
    page.get_by_text(
        "Clinical Sample Collection Details",
        exact=True
    ).wait_for(state="visible", timeout=5000)
    print("✅ On Sample Tracker page")

    # ---------- DATE FILTERS ----------
    page.locator("input[type='date']").nth(0).fill("2026-01-28")
    page.locator("input[type='date']").nth(1).fill("2026-01-28")

    # ---------- SEARCH FILTERS ----------
    page.get_by_role("textbox", name="Enter Name").fill(SEARCH_NAME)
    page.get_by_role("textbox", name="Enter Mobile No.").fill(SEARCH_MOBILE)

    # ---------- SAMPLE LOOP ----------
    for sample_name, sample_id in SAMPLE_NAME_ID_MAP.items():

        # Enter ID
        id_input = page.get_by_placeholder("Enter ID").nth(1)
        id_input.fill("")
        id_input.fill(sample_id)

        # Search
        page.get_by_role("button", name="Search").click()
        page.wait_for_timeout(1500)

        # Toggle correct sample across rows
        toggle_sample_across_rows(page, sample_name, sample_id)

        page.wait_for_timeout(1000)

    # ---------- END ----------
    page.wait_for_timeout(3000)
    browser.close()
