"""Lab Technician locator constants.

All selectors for the Report Entry workflow.
Referenced by pages/lab_technician/labtech_page.py only.
Reference: archive/labtech_search1.py, labtech_search2.py, labtech_entry.py
"""

# ── Navigation ─────────────────────────────────────────────
REPORT_ENTRY_TEXT = "Report Entry"

# ── Filters ────────────────────────────────────────────────
DATE_INPUT_SELECTOR = "input[placeholder='DD/MM/YYYY - DD/MM/YYYY']"
SEARCH_NAME_NTH = 1
SEARCH_MOBILE_NTH = 3
SEARCH_TEXTBOX_NAME = "Search Here"
APPLY_FILTER_TEXT = "Apply Filter"

# ── Department / Sub-Department Dropdowns ──────────────────
DEPT_DROPDOWN_TEXT = "None"
DEPT_OPTION_TEMPLATE = "div[title='{dept}'] div.ant-select-item-option-content"

# ── Table & Report Entry Icon ─────────────────────────────
TABLE_ROWS_SELECTOR = "tr.ant-table-row"
REPORT_ENTRY_ICON_ALT = "Report Entry"

# ── Sample Block Matching (within rows) ───────────────────
SAMPLE_SUB_ROW_SELECTOR = "div.ant-row"

# ── Sample Actions (within sub-row) ──────────────────────
ACCEPT_ACTION_TEXT = "Accept"
REJECT_ACTION_TEXT = "Reject"
REFRESH_ACTION_TEXT = "Refresh"

# ── Rejection Modal ──────────────────────────────────────
REJECTION_MODAL_SELECTOR = "div.ant-modal-body"
REJECTION_SEND_BUTTON_NAME = "Send"

# ── Sub-Department Navigation ─────────────────────────────
PREV_SUB_DEPT_BUTTON_NAME = "Previous Sub-Department"
NEXT_SUB_DEPT_BUTTON_NAME = "Next Sub-Department"

# ── Test Heading & Row ────────────────────────────────────
TEST_HEADING_TEMPLATE = 'h1:has-text("{test_name}")'
TEST_ROW_XPATH = "xpath=ancestor::tr"

# ── Parameter Fill ────────────────────────────────────────
PARAM_CONTAINER_XPATH = "xpath=ancestor::div[contains(@class,'flex')][1]"
PARAM_INPUT_SELECTOR = "input[type='text']"

# ── Save Action ───────────────────────────────────────────
SAVE_BUTTON_NAME = "Save"
CONFIRM_YES_BUTTON_NAME = "Yes"

# ── Resample Action ──────────────────────────────────────
RESAMPLE_BUTTON_NAME = "Re-sample"
RESAMPLE_REASON_XPATH_TEMPLATE = "//span[contains(text(),'{reason}')]"
ADD_SUBMIT_BUTTON_NAME = "Add & Submit"
