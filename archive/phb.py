from playwright.sync_api import sync_playwright

# ================= CONFIG =================
BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

SEARCH_NAME = "Sunita"
SEARCH_MOBILE = "8839900148"

TARGET_SAMPLES = [
    {"sub_dept": "Clinical Chemistry", "sample_name": "24-hour urine"},
    {"sub_dept": "Hematology", "sample_name": "Whole Blood/Plasma"},
    {"sub_dept": "Serology", "sample_name": "Serum"},
]
# =========================================


def search_and_toggle_samples(page, target):
    print(f"\n🔍 Searching → {target['sub_dept']} | {target['sample_name']}")

    active_tab = page.locator(".ant-tabs-tabpane-active")
    rows = active_tab.locator("tr.ant-table-row").filter(has_text=SEARCH_NAME)

    found = False
    index = 1

    for r in range(rows.count()):
        row = rows.nth(r)

        # ✅ anchor ONLY on correct sub-dept header
        sub_headers = row.locator("div.text-gray-400").filter(
            has_text=target["sub_dept"]
        )

        for s in range(sub_headers.count()):
            sub_header = sub_headers.nth(s)

            # ✅ scope strictly to THIS sub-dept section
            sample_section = sub_header.locator(
                "xpath=ancestor::div[contains(@class,'p-1')]"
            )

            blocks = sample_section.locator(
                "div.self-stretch.inline-flex.justify-between.items-center.gap-1"
            )

            for b in range(blocks.count()):
                block = blocks.nth(b)

                texts = block.locator("div.justify-start.text-slate-700")
                if texts.count() < 2:
                    continue

                sample_name = texts.nth(0).inner_text().strip()
                sample_id = texts.nth(1).inner_text().strip()

                if sample_name == target["sample_name"]:
                    toggle = block.locator("button[role='switch']")
                    toggle.wait_for(state="attached", timeout=5000)

                    state = toggle.get_attribute("aria-checked")
                    if state != "true":
                        toggle.click()
                        action = "TOGGLED ON"
                    else:
                        action = "ALREADY ON"

                    print(
                        f"{index}. "
                        f"{target['sub_dept']} | "
                        f"{sample_name} | "
                        f"{sample_id} | "
                        f"{action}"
                    )

                    index += 1
                    found = True

    if not found:
        print(f"❌ NOT FOUND → {target['sub_dept']} | {target['sample_name']}")


# ================= PLAYWRIGHT FLOW =================

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
    phlebo.wait_for(state="visible")
    phlebo.hover()
    phlebo.click()

    page.get_by_text("Sample Tracker", exact=True).click()
    print("✅ Navigated to Sample Tracker")

    page.get_by_text(
        "Clinical Sample Collection Details", exact=True
    ).wait_for(state="visible")

    # ---------- TAB SWITCH ----------
    page.locator("text=/Re-Collection/i").click()
    print("✅ Switched to Re-Collection tab")

    # ---------- DATE FILTERS ----------
    page.locator("input[type='date']").nth(0).fill("2026-02-01")
    page.locator("input[type='date']").nth(1).fill("2026-02-02")

    # ---------- SEARCH ----------
    page.get_by_role("textbox", name="Enter Name").fill(SEARCH_NAME)
    page.get_by_role("textbox", name="Enter Mobile No.").fill(SEARCH_MOBILE)
    page.get_by_role("button", name="Search").click()
    print("✅ Search applied")

    # ---------- EXECUTION ----------
    for target in TARGET_SAMPLES:
        search_and_toggle_samples(page, target)

    page.wait_for_timeout(3000)
    browser.close()
