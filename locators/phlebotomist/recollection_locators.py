# ── Navigation ───────────────────────────────────────────────
SIDEBAR_PHLEBOTOMISTS_TEXT = "Phlebotomists"
SIDEBAR_SAMPLE_TRACKER_TEXT = "Sample Tracker"

# ── Page Verification ────────────────────────────────────────
PAGE_HEADER_TEXT = "Clinical Sample Collection Details"

# ── Re-Collection Tab ────────────────────────────────────────
RECOLLECTION_TAB_LOCATOR = "text=/Re-Collection/i"
ACTIVE_TAB_SELECTOR = ".ant-tabs-tabpane-active"

# ── Filters ──────────────────────────────────────────────────
DATE_INPUT_SELECTOR = "input[type='date']"
SEARCH_NAME_LABEL = "Enter Name"
SEARCH_MOBILE_LABEL = "Enter Mobile No."
SEARCH_BUTTON_NAME = "Search"

# ── Row Parsing (ref: phlebo_rej.py) ─────────────────────────
TABLE_ROWS_SELECTOR = "tr.ant-table-row"
SUB_DEPT_LABEL_SELECTOR = "div.text-gray-400"
SAMPLE_SECTION_ANCESTOR_XPATH = "xpath=ancestor::div[contains(@class,'p-1')]"
SAMPLE_BLOCK_SELECTOR = (
    "div.self-stretch.inline-flex.justify-between.items-center.gap-1"
)
SAMPLE_TEXT_SELECTOR = "div.justify-start.text-slate-700"

# ── Toggle ───────────────────────────────────────────────────
TOGGLE_SWITCH_SELECTOR = "button[role='switch']"
TOGGLE_CHECKED_ATTR = "aria-checked"
TOGGLE_CHECKED_VALUE = "true"
