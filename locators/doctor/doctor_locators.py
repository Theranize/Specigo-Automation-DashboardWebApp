"""Doctor Report Entry locator constants.

All selectors for the Doctor Report Review workflow.
Referenced by pages/doctor/doctor_page.py only.
Reference: archive/doc.py
"""

# ── Navigation ─────────────────────────────────────────────
REPORT_ENTRY_TEXT = "Report Entry"

# ── Filters ────────────────────────────────────────────────
DATE_INPUT_SELECTOR = "input[placeholder='DD/MM/YYYY - DD/MM/YYYY']"
SEARCH_NAME_NTH = 1
SEARCH_MOBILE_NTH = 3
SEARCH_TEXTBOX_NAME = "Search Here"
APPLY_FILTER_TEXT = "Apply Filter"

# ── Table & Report Entry Icon ─────────────────────────────
TABLE_ROWS_SELECTOR = "tr.ant-table-row"
REPORT_ENTRY_ICON_ALT = "Report Entry"

# ── Sub-Department Navigation ─────────────────────────────
NEXT_SUB_DEPT_BUTTON_NAME = "Next Sub-Department"
PREV_SUB_DEPT_BUTTON_NAME = "Previous Sub-Department"

# ── Test Heading & Row ────────────────────────────────────
TEST_HEADING_TEMPLATE = 'h1:has-text("{test_name}")'
TEST_ROW_XPATH = "xpath=ancestor::tr"

# ── Parameter Fill ────────────────────────────────────────
PARAM_CONTAINER_XPATH = "xpath=ancestor::div[contains(@class,'flex')][1]"
PARAM_INPUT_SELECTOR = "input[type='text']"

# ── Save ──────────────────────────────────────────────────
SAVE_BUTTON_NAME = "Save"
CONFIRM_YES_BUTTON_NAME = "Yes"

# ── Approve ───────────────────────────────────────────────
APPROVE_BUTTON_NAME = "Approve"
FULLY_APPROVE_BUTTON_NAME = "Fully Approve"
PARTIALLY_APPROVE_BUTTON_NAME = "Partially Approve"

# ── Re-Test ───────────────────────────────────────────────
RETEST_BUTTON_NAME = "Re-Test"

# ── Re-Sample ─────────────────────────────────────────────
RESAMPLE_FILTER_TEXT = "Re-sample"
ADD_SUBMIT_BUTTON_NAME = "Add & Submit"

# ── Rectify ───────────────────────────────────────────────
RECTIFY_BUTTON_NAME = "Rectify"
RECTIFY_SUBMIT_SPAN = 'span:has-text("Submit")'
RECTIFY_REASON_TEXTBOX_NAME = "Enter The Reason"
