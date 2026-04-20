"""Phlebotomist locator constants.

All selectors for the Sample Tracker workflow.
Referenced by pages/phlebotomist/phlebotomist_page.py only.
Reference: archive/phlebo.py
"""

# ── Navigation ─────────────────────────────────────────────
SIDEBAR_PHLEBOTOMISTS_TEXT = "Phlebotomists"
SIDEBAR_SAMPLE_TRACKER_TEXT = "Sample Tracker"

# ── Page Verification ──────────────────────────────────────
PAGE_HEADER_TEXT = "Clinical Sample Collection Details"

# ── Filters ────────────────────────────────────────────────
DATE_INPUT_SELECTOR = "input[type='date']"
SEARCH_NAME_LABEL = "Enter Name"
SEARCH_MOBILE_LABEL = "Enter Mobile No."
SEARCH_ID_PLACEHOLDER = "Enter ID"
SEARCH_BUTTON_NAME = "Search"

# ── Table & Sample Blocks ─────────────────────────────────
TABLE_ROWS_SELECTOR = "tbody tr"
SAMPLE_BLOCK_SELECTOR = (
    "div.self-stretch.inline-flex.justify-between.items-center.gap-1"
)

# ── Toggle ─────────────────────────────────────────────────
TOGGLE_SWITCH_SELECTOR = "button.ant-switch"
TOGGLE_CHECKED_ATTR = "aria-checked"
TOGGLE_CHECKED_VALUE = "true"
