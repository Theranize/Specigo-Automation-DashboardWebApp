from playwright.sync_api import sync_playwright

# ================= CONFIG =================
BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

SEARCH_NAME = "Arun Kumar"
SEARCH_MOBILE = "8423456787"

ASSIGN_NOTE_TEXT = "Re-assigned after verification review."

SAMPLE_ASSIGN_DATA = [
    {
        "sample_name": "24-hour urine",
        "sample_id": "697C75FE0A564"
    },
    {
        "sample_name": "Whole Blood/Plasma",
        "sample_id": "697C675205816"
    }
]

# ================= MAIN =================
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

    # ---------- NAVIGATION (WITH HOVER) ----------
    acc = page.get_by_text("Accession", exact=True)
    acc.hover()
    acc.click()

    page.get_by_text("Re-Assignment Log", exact=True).click()
    print("✅ Navigated to Re-Assignment Log")

    # ---------- SEARCH FILTERS ----------
    page.get_by_placeholder("Search Here").nth(1).fill(SEARCH_NAME)
    page.get_by_placeholder("Search Here").nth(2).fill(SEARCH_MOBILE)
    page.get_by_role("button", name="Search").click()
    print("✅ Search applied")

    # ---------- WAIT FOR TABLE ----------
    page.wait_for_selector("tr.ant-table-row", timeout=15000)
    rows = page.locator("tr.ant-table-row")

    # =====================================================
    # SAMPLE-DRIVEN ASSIGN ENGINE
    # =====================================================
    for cfg in SAMPLE_ASSIGN_DATA:
        target_sample = cfg["sample_name"]
        target_id = cfg["sample_id"]

        print(f"\n🔍 Processing → {target_sample} | {target_id}")
        matched = False

        for r in range(rows.count()):
            row = rows.nth(r)

            sample_names = row.locator(
                "td:nth-child(4) p"
            ).all_inner_texts()

            sample_ids = row.locator(
                "td:nth-child(5) p.flex-grow"
            ).all_inner_texts()

            for name, sid in zip(sample_names, sample_ids):
                if name.strip() == target_sample and sid.strip() == target_id:
                    print(f"✅ Match found in Row {r + 1}")

                    # ---------- CLICK ASSIGN (ROW LEVEL) ----------
                    assign_btn = row.get_by_role("button", name="Assign")
                    assign_btn.scroll_into_view_if_needed()
                    assign_btn.click()

                    # ---------- ASSIGN MODAL ----------
                    note_box = page.get_by_placeholder("Add Note")
                    note_box.fill(ASSIGN_NOTE_TEXT)

                    page.locator("button").filter(
                        has_text="Assign"
                    ).last.click()

                    print(f"🚀 Assigned → {target_sample} | {target_id}")
                    matched = True
                    break

            if matched:
                break

        if not matched:
            print(f"⚠️ Not found → {target_sample} | {target_id}")

    page.wait_for_timeout(3000)
    browser.close()
