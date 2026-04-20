# ── Navigation ──────────────────────────────────────────────
ADD_PATIENT_BUTTON_TEXT = "Add Patient"
NEXT_BUTTON_NAME = "Next"
SUBMIT_BUTTON_NAME = "Submit"
PRINT_BILL_BUTTON_NAME = "Print Bill"
PRINT_BARCODE_BUTTON_NAME = "Print Barcode"

# ── Mobile Search ───────────────────────────────────────────
SEARCH_MOBILE_INPUT = "input[placeholder='Enter Phone Number'][type='number']"
SEARCH_BUTTON_NAME = "Search"
ADD_RELATIVE_TEXT = "Add Relative"

# ── Conditional Risk ───────────────────────────────────────
RISK_LEVEL_DEFAULT = "Normal"

# ── Patient Info Form ───────────────────────────────────────
SALUTATION_LABEL_TEXT = "Salutation"
SALUTATION_OPTION_XPATH = (
    "//div[@class='ant-select-item-option-content']"
    "[normalize-space()='{}']"
)
FIRST_NAME_PLACEHOLDER = "Enter First Name"
MIDDLE_NAME_PLACEHOLDER = "Enter Middle Name"
LAST_NAME_PLACEHOLDER = "Enter Last Name"
AGE_PLACEHOLDER = "Enter Age"
PIN_CODE_PLACEHOLDER = "Enter Pin code"
ADDRESS_PLACEHOLDER = "Enter Address Here"
EMAIL_PLACEHOLDER = "Enter Email"
MOBILE_INPUT = "input[name='mobile']"

# ── Relative ────────────────────────────────────────────────
RELATION_FORM_ITEM = ".ant-form-item"
RELATION_LABEL_TEXT = "Relation"
RELATION_LABEL_CONTAINS = "Relation with"
RELATION_OPTION_XPATH = (
    "//div[@class='ant-select-item-option-content']"
    "[normalize-space()='{}']"
)

# ── Error Messages ──────────────────────────────────────────
LIMIT_ERROR_TEXT = (
    "The patient limit has been reached. "
    "A maximum of 10 patients is allowed per number."
)
MOBILE_ALREADY_REGISTERED_TEXT = (
    "Mobile number is already registered. You can either add the person "
    "as a relative or use a different number."
)

# ── Test Selection ──────────────────────────────────────────
TEST_SEARCH_COMBOBOX_ROLE = "combobox"

# ── Payment ─────────────────────────────────────────────────
PAYMENT_AMOUNT_PLACEHOLDER = "Enter Amount"
BALANCE_INPUT = "input[type='number'][disabled][readonly]"

# ── Modal Selectors (Barcode / Print) ──────────────────────
FIRST_MODAL_CLOSE_XPATH = (
    "//div[@class='ant-modal css-q13irl']//div//button[@aria-label='Close']"
)
FIRST_MODAL_SELECTOR = "//div[@class='ant-modal css-q13irl']"
FINAL_MODAL_CLOSE_SELECTOR = (
    "div.ant-modal.print-modal span[aria-label='close']"
)
FINAL_MODAL_SELECTOR = "div.ant-modal.print-modal"

# ── Sample Capture ──────────────────────────────────────────
SAMPLE_SUB_DEPT_SEPARATOR = " | "
SAMPLE_ID_FOLLOWING_XPATH = "xpath=following::div[1]"

# ── Published Reports ───────────────────────────────────────
PUBLISHED_REPORTS_SIDEBAR_TEXT = "Published Report"
PUBLISHED_REPORTS_TABLE_ROWS = "tr.ant-table-row"
VIEW_REPORT_BUTTON_NAME = "View"
DOWNLOAD_REPORT_BUTTON_NAME = "Download"
