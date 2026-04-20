from playwright.sync_api import sync_playwright 
import random

BASE_URL = "https://frontenddevh1.specigo.com/"
USERNAME = "dummyadmin123"
PASSWORD = "QWERTY"

SEARCH_NAME = "Arun Kumar"                                   #create new test data as the previous one is modified
SEARCH_MOBILE = "8423456787"


SAMPLE_ACTIONS = [
    {
        "sample_name": "24-hour urine",      
        "sample_id": "697B14B8253BF",
        "action": "refresh"
    },
    {
        "sample_name": "Whole Blood/Plasma",
        "sample_id": "697B14B8675D",
        "action": "accept"
    },
    {
        "sample_name": "Whole Blood/Plasma",
        "sample_id": "697AF1AD9B20B",
        "action": "reject",
        "sub_dept": "Haematology"
    },
    {
        "sample_name": "Serum",
        "sample_id": "697B3E7969311",
        "action": "accept"
    },
    {
        "sample_name": "Serum",
        "sample_id": "697B14B826FBE",
        "action": "reject",
        "sub_dept": "Clinical Chemistry"
    }
]

CHECK_COUNT = 3
REJECTION_REASON_TEXT = "Sample integrity issue observed during verification."


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
    acc = page.get_by_text("Accession", exact=True)
    acc.wait_for(state="visible", timeout=5000)
    acc.click()
    acc.hover()
    acc.click()
    print("✅ Clicked Accession")

    page.get_by_text("Sample Verification", exact=True).click()
    print("✅ Clicked Sample Verification")

    # ---------- DATE FILTERS ----------
    page.locator("input[type='date']").nth(0).fill("2026-01-29")
    page.locator("input[type='date']").nth(1).fill("2026-01-29")

    # ---------- SEARCH FILTERS ----------
    page.get_by_placeholder("Search Here").nth(1).fill(SEARCH_NAME)
    page.get_by_placeholder("Search Here").nth(2).fill(SEARCH_MOBILE)

    # ---------- SEARCH ----------
    page.get_by_role("button", name="Search").click()
    print("✅ Search triggered")

    # ✅ WAIT 3 SECONDS AFTER SEARCH
    page.wait_for_timeout(3000)

    # =====================================================
    # ACTION ENGINE
    # =====================================================
    page.wait_for_selector("tr.ant-table-row", timeout=15000)
    rows = page.locator("tr.ant-table-row")

    executed = set()

    for r in range(rows.count()):
        row = rows.nth(r)

        blocks = row.locator(
            "div.self-stretch.inline-flex.justify-between.items-center.gap-1"
        )

        for b in range(blocks.count()):
            block = blocks.nth(b)

            name_el = block.locator("div.justify-start.text-slate-700")
            id_el = block.locator("p.font-mono")

            if not name_el.count() or not id_el.count():
                continue

            sample_name = name_el.inner_text().strip()
            sample_id = id_el.inner_text().strip()
            key = f"{sample_name}|{sample_id}"

            if key in executed:
                continue

            for cfg in SAMPLE_ACTIONS:
                if cfg["sample_name"] == sample_name and cfg["sample_id"] == sample_id:
                    executed.add(key)
                    action = cfg["action"].lower()

                    print(
                        f"🚀 ACTION → Row {r + 1} | "
                        f"{sample_name} | {sample_id} | {action.upper()}"
                    )

                    # ---------- REFRESH / ACCEPT ----------
                    if action in ("refresh", "accept"):
                        block.locator(
                            f"xpath=.//span[normalize-space()='{action.capitalize()}']"
                        ).first.click()

                        # ✅ WAIT 2 SECONDS AFTER ACTION
                        page.wait_for_timeout(2000)

                    # ---------- REJECT ----------
                    elif action == "reject":
                        block.locator(
                            "xpath=.//span[normalize-space()='Reject']"
                        ).first.click()

                        # Wait for rejection modal
                        modal = page.locator("div[role='dialog']")
                        modal.wait_for(state="visible", timeout=5000)

                        # Select sub-department
                        modal.get_by_text(cfg["sub_dept"], exact=True).click()

                        # Select rejection reasons
                        cbs = modal.locator("input[type='checkbox']")
                        for i in random.sample(
                            range(cbs.count()), min(CHECK_COUNT, cbs.count())
                        ):
                            cbs.nth(i).check()

                        # Enter rejection reason
                        editor = modal.get_by_role(
                            "textbox",
                            name="Editor editing area: main. Press Alt+0 for help."
                        )
                        editor.type(REJECTION_REASON_TEXT, delay=30)

                        # Send rejection
                        modal.get_by_role("button", name="Send").click()

                        # Wait for modal to close
                        modal.wait_for(state="hidden", timeout=5000)

                        # ✅ WAIT 2 SECONDS AFTER REJECT
                        page.wait_for_timeout(2000)

                    break  # stop scanning SAMPLE_ACTIONS

    page.wait_for_timeout(3000)
    browser.close()
