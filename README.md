# Specigo E2E Automation — Playwright + Python

End-to-end test automation framework for a multi-role clinical lab management system.
Built with **Playwright (sync API) + Python + Pytest**.

**Base URL:** `https://frontenddevh1.specigo.com/`

---

## Table of Contents

0. [Prerequisites](#0-prerequisites)
1. [Architecture Overview](#1-architecture-overview)
2. [Quick Start](#2-quick-start)
3. [Directory Structure](#3-directory-structure)
4. [Pages](#4-pages)
5. [Flows](#5-flows)
6. [Tests](#6-tests)
7. [Fixtures](#7-fixtures)
8. [State Management](#8-state-management)
9. [Locators](#9-locators)
10. [Test Data (DDT)](#10-test-data-ddt)
11. [Utils](#11-utils)
12. [Config](#12-config)
13. [Artifacts & Reports](#13-artifacts--reports)
14. [Key Coding Patterns](#14-key-coding-patterns)
15. [E2E Flow — Role Sequence](#15-e2e-flow--role-sequence)
16. [Role Actions Reference](#16-role-actions-reference)
17. [DDT Structure & Acceptable Values](#17-ddt-structure--acceptable-values)

---

## 0. Prerequisites

### Requirements
- **Python 3.14** — [Download](https://www.python.org/downloads/)
- **Allure CLI** (for HTML reports) — [Install guide](https://allurereport.org/docs/install/)

### Virtual Environment Setup

The project uses a virtual environment located in the `Test/` folder. Run the following commands once from the **project root**:

**Create the virtual environment inside `Test/`:**
```bash
python -m venv Test
```

**Install all dependencies from `requirements.txt`:**
```bash
Test\Scripts\pip install -r requirements.txt
```

**Install Playwright browsers:**
```bash
Test\Scripts\playwright install
```

> **Important:** Always use `Test\Scripts\pytest.exe` (or `run.bat`) to run tests — never the system `pytest`. The `Test/` folder is the venv and must not be renamed or moved.

---

## 1. Architecture Overview

```
Tests  →  Flows  →  Pages (inherit BasePage)  →  Locators  →  Playwright
                         ↕
                   state/runtime_state.py
```

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Pages** | `pages/` | UI interaction; all inherit `BasePage` |
| **Flows** | `flows/` | Business logic orchestrators; return `{completed, error_found, error_message}` |
| **Tests** | `tests/` | Thin assertions; call flows and assert results |
| **State** | `state/runtime_state.py` | Shared session dict across flows (patient_id, samples, etc.) |
| **Locators** | `locators/` | CSS/XPath selectors organized by role |
| **Test Data** | `test_data/` | DDT JSON files per role/scenario |

---

## 2. Quick Start

Use `run.bat` from the project root. It wraps `.\Test\Scripts\pytest.exe` with `-v --tb=short` automatically.

```batch
run e2e                  # All E2E tests
run acceptance           # E2E acceptance (happy path)
run rejection            # E2E rejection / recollection flows
run rectification        # E2E rectification flows
run regression           # All regression tests
run smoke                # Smoke tests
run all                  # Entire test suite
```

**Run a specific file or pass custom args:**

```batch
run tests/e2e/acceptance/test_e2e_p5_relative_acceptance.py
run -m doctor -v
```

**Generate Allure HTML report (manual, after run):**

```batch
allure generate reports/allure-results -o reports/allure-report --clean
```

> `run.bat` always uses `.\Test\Scripts\pytest.exe` (venv). Never use the system `pytest`.

---

## 3. Directory Structure

```
D:/automation/playwright/
├── .claude/
│   └── test_run_session.json       # E2E test → patient ID mapping
├── config/
│   ├── test_config.yaml            # Browser/timeout settings
│   └── urls.yaml                   # Base URL
├── fixtures/
│   ├── browser_fixtures.py         # browser_instance, page
│   ├── data_fixtures.py            # 10 DDT data fixtures
│   └── session_fixtures.py         # login_as
├── flows/
│   ├── login_flow.py
│   ├── logout_flow.py
│   ├── front_desk_flow.py
│   ├── accession_flow.py
│   ├── phlebotomist_flow.py
│   ├── labtech_flow.py
│   ├── doctor_flow.py
│   ├── reassignment_flow.py
│   └── recollection_flow.py
├── locators/                       # Selectors by role
├── pages/
│   ├── base_page.py
│   ├── accession/
│   ├── doctor/
│   ├── front_desk/
│   ├── lab_technician/
│   ├── login/
│   ├── logout/
│   └── phlebotomist/
├── state/
│   └── runtime_state.py
├── test_data/                      # DDT JSON per role
├── tests/
│   ├── e2e/
│   │   ├── acceptance/
│   │   └── rejection/
│   └── regression/
├── utils/
├── conftest.py
└── pytest.ini
```

---

## 4. Pages

All page classes inherit `BasePage` which provides shared utility methods.

### BasePage (`pages/base_page.py`)

Core utilities available to all page objects.

| Method | Description |
|--------|-------------|
| `wait_for_navigation(url_pattern, timeout)` | Wait for URL to match pattern |
| `wait_for_idle(seconds)` | Explicit wait for UI to settle |
| `scroll_down(pixels)` | Scroll page by pixel amount |
| `scroll_to_element(locator)` | Scroll element into viewport |
| `click_button(name, scroll)` | Click button by accessible role name |
| `click_text(text, exact)` | Click element by visible text |
| `fill_textbox(name, value)` | Fill input by accessible name |
| `fill_placeholder(placeholder, value)` | Fill input by placeholder text |
| `type_into(locator, value, delay)` | Type into locator with configurable delay |
| `select_antd_option(dropdown_selector, option_xpath)` | Select AntD dropdown option |
| `get_attribute_value(selector, attribute, nth)` | Read attribute from element |
| `get_input_value(selector)` | Read current value of input field |

---

### LoginPage (`pages/login/login_page.py`)

| Method | Description |
|--------|-------------|
| `login(username, password)` | Enter credentials and submit; waits until URL leaves `/login` |

---

### LogoutPage (`pages/logout/logout_page.py`)

| Method | Description |
|--------|-------------|
| `logout()` | Click profile icon → logout heading → confirmation button |

---

### FrontDeskPage (`pages/front_desk/front_desk_page.py`)

Handles patient registration, test assignment, payment, and published reports.

| Method | Description |
|--------|-------------|
| `click_add_patient()` | Click 'Add Patient' and navigate to general info page |
| `select_risk_level(risk_level)` | Select risk level from dropdown if not default |
| `click_next()` | Scroll and click Next via JS dispatch |
| `click_submit()` | Click Submit and wait for network idle |
| `search_mobile(mobile)` | Enter mobile in search field |
| `click_search()` | Click Search and wait for results |
| `select_patient_card(card_display_name)` | Select existing patient from search results |
| `click_add_relative()` | Click 'Add Relative' after search |
| `select_relation(relation_name)` | Open relation dropdown (label-based XPath, AntD-aware) |
| `detect_error()` | Check for error toasts (limit reached, already registered) |
| `select_salutation(value)` | Select salutation from AntD dropdown (handles dot formatting) |
| `fill_patient_name(first, middle, last)` | Fill all three name fields |
| `select_gender(gender)` | Click gender radio button |
| `fill_age(age)` | Fill age field |
| `fill_pin_code(pin)` | Fill pincode; triggers auto-fill of State/City/District (3s wait) |
| `fill_address(address)` | Fill address textarea |
| `fill_email(email)` | Fill email field |
| `fill_mobile(mobile)` | Fill bottom mobile field |
| `get_mobile_value()` | Read current mobile field value |
| `fill_pin_code_if_empty(pin)` | Conditional pincode fill (only if empty) |
| `fill_address_if_empty(address)` | Conditional address fill |
| `fill_email_if_empty(email)` | Conditional email fill |
| `fill_mobile_if_empty(mobile)` | Conditional mobile fill |
| `add_test(test_name)` | Search and select test in AntD combobox |
| `fill_payments(home_collection, cash, online)` | Fill three payment amount fields |
| `get_balance()` | Read auto-calculated balance |
| `click_print_bill()` | Click Print Bill and handle new tab |
| `click_print_barcode()` | Click Print Barcode and wait for modal |
| `capture_samples(tests)` | Extract sample IDs and metadata from barcode modal |
| `close_barcode_modals()` | Two-step modal close sequence |
| `navigate_to_published_reports()` | Expand Patients sidebar → Published Reports |
| `find_published_report(patient_name)` | Find patient report row by name |
| `view_report(row)` | Click View/Download on a report row |

---

### AccessionPage (`pages/accession/accession_page.py`)

Sample verification and rejection workflow.

| Method | Description |
|--------|-------------|
| `navigate_to_sample_verification()` | Click Accession sidebar → Sample Verification |
| `wait_for_table_rows()` | Wait for result table rows to appear |
| `apply_date_filters(from_date, to_date)` | Fill from/to date inputs (DD/MM/YYYY or YYYY-MM-DD) |
| `fill_search_name(name)` | Enter patient name in search field |
| `fill_search_mobile(mobile)` | Enter mobile in search field |
| `click_search()` | Click Search and wait for table to load |
| `find_sample_block(sample_name, sample_id)` | Find block matching both name AND sample ID |
| `find_sample_block_by_name(sample_name)` | Find block by name only (for recollected samples) |
| `click_refresh(block)` | Click Refresh action within sample block |
| `click_accept(block)` | Click Accept action within sample block |
| `click_reject(block)` | Click Reject action (opens rejection modal) |
| `wait_for_rejection_modal()` | Wait for and return rejection modal locator |
| `handle_rejection_modal(modal, rejection_config)` | Complete rejection form and submit |

---

### ReassignmentPage (`pages/accession/reassignment_page.py`)

Re-Assignment Log workflow for rejected samples.

| Method | Description |
|--------|-------------|
| `navigate_to_reassignment_log()` | Click Accession sidebar → Re-Assignment Log |
| `fill_search_filters(name, mobile)` | Fill name and mobile search inputs |
| `click_search()` | Click Search and wait for results |
| `wait_for_rows()` | Wait for reassignment table rows |
| `find_row(sample_name)` | Find row by sample name |
| `assign_sample(row, note)` | Click Assign, fill note in modal, confirm, wait for close |

---

### PhlebotomistPage (`pages/phlebotomist/phlebotomist_page.py`)

Sample toggle workflow (mark samples collected/not collected).

| Method | Description |
|--------|-------------|
| `navigate_to_sample_tracker()` | Click Phlebotomists sidebar → Sample Tracker |
| `verify_page_header()` | Verify Sample Tracker page header is visible |
| `apply_date_filters(from_date, to_date)` | Fill from/to date inputs |
| `fill_search_name(name)` | Fill patient name search |
| `fill_search_mobile(mobile)` | Fill mobile search |
| `fill_search_id(sample_id)` | Clear and fill sample ID search field |
| `click_search()` | Click Search and wait for table |
| `find_sample_block(sample_name, sample_id)` | Find block matching name AND sample ID |
| `toggle_sample(block, action)` | Toggle switch; returns `toggled_on / toggled_off / already_on / already_off` |

---

### RecollectionPage (`pages/phlebotomist/recollection_page.py`)

Re-Collection tab workflow for recollected samples.

| Method | Description |
|--------|-------------|
| `navigate_to_sample_tracker()` | Navigate to Sample Tracker page |
| `verify_page_header()` | Verify page header is visible |
| `switch_to_recollection_tab()` | Click Re-Collection tab |
| `apply_date_filters(from_date, to_date)` | Fill from/to date inputs |
| `fill_search_name(name)` | Enter patient name |
| `fill_search_mobile(mobile)` | Enter mobile number |
| `click_search()` | Click Search and wait for results |
| `wait_for_rows()` | Wait for table rows in active tab |
| `find_sample_block(patient_name, sub_department, sample_name)` | Find block by sub_dept + name; prefers OFF-toggled samples |
| `get_block_sample_id(block)` | Extract sample ID from block |
| `toggle_sample(block, action)` | Toggle switch; returns `toggled_on / toggled_off / already_on / already_off` |

---

### LabTechPage (`pages/lab_technician/labtech_page.py`)

Report Entry form filling with parameter entry, saving, and sample rejection.

| Method | Description |
|--------|-------------|
| `wait_for_report_entry_visible()` | Wait for 'Report Entry' menu to appear |
| `click_report_entry_menu()` | Click Report Entry navigation item |
| `apply_date_filters(from_date, to_date)` | Fill AntD RangePicker (DD/MM/YYYY or YYYY-MM-DD) |
| `select_department(department)` | Select department from dropdown |
| `select_sub_department(sub_department)` | Type first 3 chars and click exact match |
| `fill_search_name(name)` | Fill patient name search |
| `fill_search_mobile(mobile)` | Fill mobile search |
| `click_apply_filter()` | Click Apply Filter and wait for results |
| `wait_for_patient_rows()` | Wait for patient result rows |
| `find_sample_sub_row_by_name(sample_name, anchor_id)` | Find sub-row by name (optional anchor) |
| `find_sample_sub_row(sample_name, sample_id)` | Find sub-row matching name AND sample ID |
| `find_sample_sub_row_by_action(sample_name, action_text, anchor_id)` | Find sub-row by name + action button text |
| `click_accept_sample(sub_row)` | Click Accept on sample |
| `click_refresh_sample(sub_row)` | Click Refresh on sample |
| `click_reject_sample(sub_row)` | Click Reject on sample (opens modal) |
| `handle_rejection_modal(rejection_config)` | Complete rejection modal form |
| `open_report_entry(sample_id)` | Hover row until Report Entry icon appears; match by ID |
| `reset_to_first_sub_department()` | Click Previous until disabled |
| `click_next_sub_department()` | Click Next Sub-Department; returns `False` if at last |
| `_scroll_until_test_visible(test_name, max_scrolls)` | Scroll to make test heading visible |
| `find_test_row_on_current_page(test_name)` | Find test row on current sub-dept page |
| `traverse_and_find_test(test_name)` | Reset to first sub-dept and traverse until test found |
| `fill_parameter(row, param_name, value)` | Fill a single parameter input with retries |
| `_wait_until_enabled(button, timeout)` | Poll button locator until enabled |
| `save_test(row)` | Click Save and handle confirmation dialog |
| `resample_test(row, reason)` | Click Resample, fill reason, submit |

---

### DoctorPage (`pages/doctor/doctor_page.py`)

Doctor Report Review: parameter entry, approval, retest, resample, and rectification.

| Method | Description |
|--------|-------------|
| `wait_for_report_entry_visible()` | Wait for Report Entry menu |
| `click_report_entry_menu()` | Click Report Entry navigation |
| `apply_date_filters(from_date, to_date)` | Fill AntD RangePicker |
| `fill_search_name(name)` | Fill patient name search |
| `fill_search_mobile(mobile)` | Fill mobile search |
| `click_apply_filter()` | Click Apply Filter and wait |
| `wait_for_patient_rows()` | Wait for patient rows to appear |
| `open_report_entry(sample_id)` | Hover row and click Report Entry icon; match by ID |
| `is_sub_dept_visible(sub_dept_name)` | Check if sub-dept heading is visible |
| `navigate_to_sub_dept(sub_dept_name)` | Navigate Next/Previous until sub-dept visible (max 20 attempts) |
| `find_test_row(test_name, max_scrolls)` | Locate test row in current sub-dept |
| `fill_parameter(row, param_name, value)` | Fill single parameter with retries |
| `fill_parameters(row, parameters)` | Fill all parameters; returns error string or `None` |
| `_wait_until_enabled(button, timeout)` | Poll button until enabled |
| `save_test(row)` | Click Save and handle confirmation; handles multi-row test layouts |
| `handle_approve(row, action)` | Click Approve → Fully Approve or Partially Approve dialog |
| `handle_retest(row)` | Click Re-Test and confirm Yes |
| `handle_resample(row, reason)` | Click Resample, select reason (checkbox or textbox), submit |
| `handle_rectify(row, rectification)` | Click Rectify, select reason, fill Others if needed, Submit → confirm |

---

## 5. Flows

Flow functions orchestrate page calls into complete business workflows. They always return:

```python
{"completed": bool, "error_found": bool, "error_message": str | None}
```

### login_flow.py

| Function | Description |
|----------|-------------|
| `execute_login(page, role, credentials)` | Create `LoginPage` and call `login()` |

### logout_flow.py

| Function | Description |
|----------|-------------|
| `execute_logout(page)` | Create `LogoutPage` and call `logout()` |

### front_desk_flow.py

| Function | Description |
|----------|-------------|
| `execute_front_desk_registration(page, patient_entry, test_payment_entry)` | Full registration: search → fill forms → add tests → payments → print bill/barcode → capture samples into runtime state |
| `execute_front_desk_published_reports(page, patient_name)` | Navigate to Published Reports and verify patient report is visible |

### accession_flow.py

| Function | Description |
|----------|-------------|
| `execute_accession_flow(page, accession_entry)` | Navigate → search → apply actions (refresh / accept / reject) per sample rule; matches samples from runtime state |

### phlebotomist_flow.py

| Function | Description |
|----------|-------------|
| `execute_phlebotomist_flow(page, phlebo_entry)` | Navigate → search → toggle samples on/off per DDT instructions |

### labtech_flow.py

| Function | Description |
|----------|-------------|
| `execute_labtech_search(page, search_entry)` | Search patient, apply sample actions (accept/refresh/reject), open Report Entry |
| `execute_labtech_tests(page, tests_entry)` | Traverse sub-departments, fill test parameters, save or resample each test |

### doctor_flow.py

| Function | Description |
|----------|-------------|
| `execute_doctor_flow(page, patient_entry)` | Full doctor workflow: search → navigate sub-depts → fill parameters → perform action per test (approve / partial_approve / retest / resample / rectify) |

### reassignment_flow.py

| Function | Description |
|----------|-------------|
| `execute_reassignment_flow(page, reassignment_entry)` | Navigate Re-Assignment Log → search → assign each rejected sample to a phlebotomist |

### recollection_flow.py

| Function | Description |
|----------|-------------|
| `execute_recollection_flow(page, recollection_entry)` | Switch to Re-Collection tab → search → toggle collected samples → capture new sample IDs into runtime state |

---

## 6. Tests

### E2E — Acceptance (`tests/e2e/acceptance/`)

| File | Patient | Scenario |
|------|---------|----------|
| `test_e2e_acceptance.py` | P1 | Full happy-path: all 7 tests, all 5 stages accept/approve |
| `test_e2e_p3_partial_approve.py` | P3 | Phlebo 3/4 ON, Accession 2/3, LT 1/2, Doctor approves RFT+LFT |
| `test_e2e_p4_rectification.py` | P4 | Full acceptance + Doctor rectifies RFT and LFT |
| `test_e2e_p5_relative_acceptance.py` | P5 | Select existing relative (Wife) → full acceptance all 7 tests |
| `test_e2e_p7_limit_error.py` | P7 | Add-relative limit error — 10-patient cap reached |
| `test_e2e_p8_new_patient_acceptance.py` | P8 | New patient Priya Sharma → full acceptance all 7 tests |
| `test_e2e_p12_relative_acceptance.py` | P12 | Add new relative Vikram Kumar → full acceptance + Doctor rectify |
| `test_e2e_p14_partial_approve.py` | P14 | New patient Sanjay Mehta → 3 tests, Doctor partial_approve |

### E2E — Rejection (`tests/e2e/rejection/`)

| File | Patient | Scenario |
|------|---------|----------|
| `test_e2e_p2_rejection.py` | P2 | 3-cycle rejection: Acc:Serum → LT:24h urine → Dr:LFT resample → partial_approve |
| `test_e2e_p6_rejection.py` | P6 | 3-cycle rejection: Acc:Urine → LT:Serum → Dr:CBC resample → full approve |
| `test_e2e_p9_new_patient_rejection.py` | P9 | New patient Rohan Desai → 3-cycle rejection → full approve |
| `test_e2e_p13_partial_rejection.py` | P13 | Acc:Serum rejected, LT:24h urine rejected; Doctor approves all (local date) |

### Regression (`tests/regression/`)

| File | Scope |
|------|-------|
| `test_login_smoke.py` | Login smoke for all roles |
| `test_front_desk_regression.py` | Patient registration end-to-end |
| `test_accession_regression.py` | Sample verification actions |
| `test_phlebotomist_regression.py` | Sample toggle actions |
| `test_labtech_regression.py` | Report entry and parameter fill |
| `test_doctor_regression.py` | Doctor review, approve, rectify |
| `test_reassignment_regression.py` | Re-assignment log |
| `test_recollection_regression.py` | Re-collection tab toggle |

### Pytest Markers

| Marker | Usage |
|--------|-------|
| `smoke` | Quick login/navigation checks |
| `regression` | Role-wise regression tests |
| `e2e` | Full end-to-end multi-role tests |
| `acceptance` | Happy-path acceptance flows |
| `rejection` | Rejection / recollection flows |
| `labtech` | Lab technician report entry |
| `doctor` | Doctor report review |

---

## 7. Fixtures

### browser_fixtures.py

| Fixture | Scope | Description |
|---------|-------|-------------|
| `browser_instance` | session | Launch Chromium maximized; yields `{browser, context, base_url}`; records video |
| `page` | function | Fresh page per test; navigates to `/login`; closes after test |

### session_fixtures.py

| Fixture | Scope | Description |
|---------|-------|-------------|
| `login_as` | function | Yields callable `do_login(role: str)`; auto-logout teardown; clears runtime state |

### data_fixtures.py

| Fixture | JSON Source |
|---------|-------------|
| `login_credentials` | `test_data/login/login_ddt.json` |
| `front_desk_patient_data` | `test_data/front_desk/patient_data.json` |
| `front_desk_test_payment_data` | `test_data/front_desk/test_payment_data.json` |
| `phlebotomist_actions_data` | `test_data/phlebotomist/phlebotomist_actions.json` |
| `accession_actions_data` | `test_data/accession/accession_actions.json` |
| `labtech_search_data` | `test_data/lab_technician/labtech_search.json` |
| `labtech_tests_data` | `test_data/lab_technician/labtech_tests.json` |
| `doctor_actions_data` | `test_data/doctor/doctor_actions.json` |
| `reassignment_actions_data` | `test_data/accession/reassignment_actions.json` |
| `doctor_rectify_actions_data` | `test_data/doctor/doctor_rectify_actions.json` |

---

## 8. State Management

**File:** `state/runtime_state.py`

Global state dict shared across all flows in a test session.

| Function | Description |
|----------|-------------|
| `set_value(key, val)` | Set a value in state |
| `get_value(key)` | Get a value from state |
| `clear()` | Reset all state (lists cleared, scalars set to `None`) |
| `add_sample(name, sub_department, id, index)` | Append sample entry to `samples` list |
| `get_samples()` | Return full samples list |
| `get_state_snapshot()` | Return a shallow copy of the entire state dict |

**Tracked Keys:**

| Key | Type | Description |
|-----|------|-------------|
| `current_role` | str | Active logged-in role |
| `username` | str | Username of active session |
| `login_timestamp` | str | Time of last login |
| `patient_id` | str | Current patient ID (e.g. `P1`) |
| `patient_name` | str | Patient display name |
| `patient_mobile` | str | Patient mobile number |
| `mobile_number` | str | Mobile used for search |
| `mobile_auto_filled` | bool | Whether mobile was auto-populated |
| `samples` | list | Captured sample dicts `{name, sub_dept, id, index}` |
| `tests` | list | Test names processed |
| `balance` | str | Auto-calculated balance from FD payment |
| `approval_status` | str | Doctor approval outcome |
| `new_id::<key>` | str | Dynamic keys for recollected sample IDs |

---

## 9. Locators

All selectors are centralized under `locators/`, organized by role.

| Module | Role |
|--------|------|
| `base_locators.py` | Shared constants (button names, common XPath) |
| `accession/accession_locators.py` | Sample Verification selectors |
| `accession/reassignment_locators.py` | Re-Assignment Log selectors |
| `doctor/doctor_locators.py` | Doctor Report Review selectors |
| `front_desk/front_desk_locators.py` | Patient registration selectors |
| `lab_technician/labtech_locators.py` | Report Entry selectors |
| `login/login_locators.py` | Login form selectors |
| `logout/logout_locators.py` | Logout menu selectors |
| `phlebotomist/phlebotomist_locators.py` | Sample Tracker selectors |
| `phlebotomist/recollection_locators.py` | Re-Collection tab selectors |

**Common constants from `base_locators.py`:**

```python
CONFIRM_YES_BUTTON = "Yes"
CONFIRM_NO_BUTTON = "No"
DATE_RANGE_PLACEHOLDER = "DD/MM/YYYY - DD/MM/YYYY"
APPLY_FILTER_TEXT = "Apply Filter"
REPORT_ENTRY_TEXT = "Report Entry"
NEXT_SUB_DEPT_BUTTON = "Next Sub-Department"
PREV_SUB_DEPT_BUTTON = "Previous Sub-Department"
SAVE_BUTTON = "Save"
```

---

## 10. Test Data (DDT)

All test decisions come from JSON. No patient IDs or scenario data are hardcoded in `.py` files.

```
test_data/
├── login/login_ddt.json
├── front_desk/
│   ├── patient_data.json
│   └── test_payment_data.json
├── accession/
│   ├── accession_actions.json
│   └── reassignment_actions.json
├── phlebotomist/phlebotomist_actions.json
├── lab_technician/
│   ├── labtech_search.json
│   └── labtech_tests.json
├── doctor/
│   ├── doctor_actions.json
│   └── doctor_rectify_actions.json
└── e2e/
    ├── acceptance.json
    ├── b1_accession_rejection.json
    ├── b2_labtech_rejection.json
    ├── b3_doctor_resample.json
    ├── b4_add_relative_rectification.json
    └── bc_combined_rejection.json
```

**DDT lookup pattern:**

```python
from utils.file_utils import load_json
from pathlib import Path

DATA = load_json(Path("test_data/role/file.json"))

def _entry(lst, key, val):
    return next(e for e in lst if e[key] == val)

entry = _entry(DATA["patients"], "patient_id_ref", "P1")
result = execute_some_flow(page, entry)
assert result["completed"]
```

**Patient ID registry** — `.claude/test_run_session.json`:

| Patient | Name | Mobile | Scenario |
|---------|------|--------|----------|
| P1 | Aditya Kumar Mishra | 7777777777 | Full acceptance — all 7 tests |
| P2 | Aditya Kumar Mishra | 7777777777 | 3-cycle rejection → partial_approve |
| P3 | Aditya Kumar Mishra | 7777777777 | Partial pipeline — Doctor approves RFT+LFT |
| P4 | Aditya Kumar Mishra | 7777777777 | Full acceptance + Doctor rectifies RFT+LFT |
| P5 | Sunita Kumari Mishra (Wife) | 8839900148 | Select existing relative → full acceptance |
| P6 | Aditya Kumar Mishra | 7777777777 | 3-cycle rejection → full approve |
| P7 | — | 8839900148 | Add-relative limit error (10-patient cap) |
| P8 | Priya Sharma | 8900000005 | New patient → full acceptance |
| P9 | Rohan Desai | 8900000006 | New patient → 3-cycle rejection → full approve |
| P10 | Kavita Nair | 8900000007 | New patient → Acc:24h urine reject + Doctor rectify LFT |
| P11 | Rajesh Kumar | 9999999999 | Duplicate mobile error |
| P12 | Vikram Kumar Mishra (Brother) | 7777777777 | Add new relative → full acceptance + Doctor rectify |
| P13 | Aditya Kumar Mishra | 7777777777 | Partial rejection Acc+LT, Doctor approves (local date) |
| P14 | Sanjay Mehta | 8900000008 | New patient → 3 tests, Doctor partial_approve |

> Never write `pid = "P1"` in a `.py` file. Patient IDs live only in `.claude/test_run_session.json`.

---

## 11. Utils

| Module | Description |
|--------|-------------|
| `file_utils.py` | `load_json(path)`, `load_yaml(path)` |
| `reporting.py` | Generate HTML/JSON/CSV/Allure summary reports |
| `phase_tracker.py` | Track and log test phase progress |
| `logger.py` | Logging utilities |
| `error_detector.py` | Detect UI error toasts and alerts |
| `test_helpers.py` | Shared test helper functions |
| `wait_utils.py` | Custom wait condition utilities |

---

## 12. Config

### `config/test_config.yaml`

```yaml
timeout: 30000        # Page timeout: 30 seconds
slow_mo: 50           # Action delay: 50ms
headless: false       # Run with visible browser
```

### `config/urls.yaml`

```yaml
base_url: "https://frontenddevh1.specigo.com/"
```

### `pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -s -v --tb=short --html=reports/html/pytest_report.html \
          --json-report --json-report-file=reports/json/pytest_report.json \
          --alluredir=reports/allure-results
markers = smoke, regression, e2e, acceptance, rejection, labtech, doctor
```

---

## 13. Artifacts & Reports

| Output | Path |
|--------|------|
| Failure screenshots | `artifacts/failures/` |
| Success screenshots | `artifacts/success/` |
| Traces (failures only) | `artifacts/traces/` |
| Test videos | `artifacts/videos/` |
| Pytest HTML | `reports/html/pytest_report.html` |
| Pytest JSON | `reports/json/pytest_report.json` |
| Allure raw data | `reports/allure-results/` |
| Allure HTML | `reports/allure-report/` (after generate) |
| Summary HTML/JSON/CSV | `reports/summary_report.*` |
| Phase report | `reports/patient_phase_report.html` |

---

## 14. Key Coding Patterns

### AntD Quirks

```python
# Overlays intercept normal clicks — use JS dispatch
el.evaluate("el => el.click()")

# Combobox with pre-selected item — force click
combobox.click(force=True)

# AntD search combobox — use type() with delay, NOT fill()
page.type(selector, value, delay=80)

# AntD IDs shift dynamically — always use label-based XPath
# NEVER: page.locator("#rc_select_3")
# CORRECT: page.locator("//label[text()='Relation']/following::div[1]")
```

### General Rules

- Scroll before interacting with below-fold elements
- Payment/number inputs → `type()`, not `fill()`
- `SEARCH_MOBILE_NTH = 3` on LabTech and Doctor pages (4 search fields exist, 0-indexed)
- Sample capture: `get_by_text("SampleName -", exact=True)` then `xpath=following::div[1]`
- Print Bill opens new tab → switch back with `page.context.pages[0].bring_to_front()`
- Sub-dept navigation: bidirectional Next/Prev loop, max 20 attempts

### MNC Standard (required on all new code)

- Type hints on all parameters and return values
- Docstrings on all classes and public methods
- `BasePage` inheritance for all page classes
- Section comments: `# --- Section Name ---`

---

## 15. E2E Flow — Role Sequence

```
Step 1 — Front Desk
  • Register patient (name, gender, age, address, mobile)
  • Assign tests
  • Complete payment
  • Print barcode → capture sample IDs into runtime state

Step 2 — Phlebotomist
  • Search patient by mobile
  • Toggle samples to "collected"

Step 3 — Accession
  • Search patient
  • Accept / Reject / Refresh each sample

Step 4 — Lab Technician
  • Open Report Entry
  • Navigate sub-departments
  • Fill test parameters
  • Save each test

Step 5 — Doctor
  • Open Report Entry
  • Navigate sub-departments
  • Fill parameters
  • Perform action: approve | partial_approve | retest | resample | rectify
```

**Doctor action reference:**

| Action | Steps |
|--------|-------|
| `approve` | Fill params → Save → Approve → "Fully Approve" dialog |
| `partial_approve` | Fill params → Save → Approve → "Partially Approve" dialog |
| `retest` | Click Re-Test → Confirm Yes |
| `resample` | Click Resample → select/enter reason → Submit |
| `rectify` | Fill params → Rectify (no Save) → dialog → reason → optional Others text → Submit → Yes |

---

## 16. Role Actions Reference

Detailed breakdown of every action each role performs in the system.

---

### Front Desk

| Action | Description |
|--------|-------------|
| Search patient | Enter mobile number → click Search → results appear |
| Select existing patient | Click patient card from search results |
| Add new patient | Click Add Patient → fill registration form |
| Add new relative | Click Add Relative → fill relative details form |
| Select existing relative | Search by mobile → select relative card |
| Fill patient details | Salutation, first/middle/last name, gender, risk level, age, DOB, mobile, email, address |
| Assign tests | Search test by name in combobox → select → repeat for each test |
| Process payment | Fill home collection, cash, online payment amounts |
| Print bill | Click Print Bill → new tab opens → switch back to original tab |
| Print barcode | Click Print Barcode → barcode modal → capture sample IDs → close modal |

---

### Phlebotomist

| Action | Description |
|--------|-------------|
| Apply date filter | Set from_date and to_date on Sample Tracker |
| Search patient | Enter name + mobile → click Search |
| Toggle sample ON | Mark sample as collected (switch toggle to ON) |
| Toggle sample OFF | Mark sample as not collected (switch toggle to OFF) |
| Re-Collection: switch tab | Navigate to Re-Collection tab |
| Re-Collection: toggle | Toggle recollected sample ON → capture new sample ID into runtime state |

---

### Accession

| Action | Description |
|--------|-------------|
| Apply date filter | Set from_date and to_date on Sample Verification |
| Search patient | Enter name + mobile → click Search |
| Accept sample | Click Accept on a sample block → sample marked received |
| Reject sample | Click Reject → rejection modal → select reason → enter notes → Submit |
| Refresh sample | Click Refresh on a sample block → re-checks sample status |
| Re-accept (recollected) | After recollection: search new sample ID → Accept again |
| Navigate Re-Assignment Log | Accession sidebar → Re-Assignment Log → search → assign rejected sample to phlebotomist |

---

### Lab Technician

| Action | Description |
|--------|-------------|
| Apply date filter | Set from_date and to_date on Report Entry |
| Select sub-department | Type first 3 chars → pick exact match from dropdown |
| Search patient | Enter name + mobile → click Apply Filter |
| Accept sample | Click Accept on sample row |
| Reject sample | Click Reject → rejection modal → select reason → Submit |
| Refresh then accept | Click Refresh on sample row → then Accept |
| Open Report Entry | Hover patient row → click Report Entry icon (matched by sample ID) |
| Navigate sub-departments | Previous / Next Sub-Department buttons, max 20 attempts |
| Fill test parameters | Enter numeric values in each parameter field (e.g. Haemoglobin, RBC, Creatinine) |
| Save test | Click Save → confirmation dialog → Confirm |
| Resample test | Click Resample → enter reason text → Submit |

---

### Doctor

| Action | Description |
|--------|-------------|
| Apply date filter | Set from_date and to_date on Report Entry |
| Search patient | Enter name + mobile → click Apply Filter |
| Open Report Entry | Hover patient row → click Report Entry icon |
| Navigate sub-departments | Previous / Next Sub-Department buttons, max 20 attempts |
| Fill test parameters | Enter values in parameter fields for the test |
| Approve (full) | Fill params → Save → Approve → click "Fully Approve" in dialog |
| Approve (partial) | Fill params → Save → Approve → click "Partially Approve" in dialog |
| Retest | Click Re-Test → confirm Yes |
| Resample | Click Resample → select/enter reason → Submit |
| Rectify | Fill params → click Rectify (no Save) → reason dialog → select reason → fill "Others" if needed → Submit → confirm Yes |

---

## 17. DDT Structure & Acceptable Values

All test data lives in `test_data/`. No scenario data or patient IDs are hardcoded in `.py` files.

---

### A. Front Desk — Patient Data
**File:** `test_data/front_desk/patient_data.json`  
**Root key:** `patients[]`  
**Lookup:** `patient_id_ref`

```json
{
  "patient_id_ref": "P1",
  "scenario": "Free-text description of the scenario",

  "patient_intent": {
    "patient_type":          "existing_primary | existing_relative | new_user",
    "search_before_add":     true | false,
    "mobile_number_status":  "registered | unregistered",
    "relative_action":       "none | select_existing_relative | add_new_relative",
    "card_display_name":     "Name shown on patient card (empty string if new user)"
  },

  "expected_error": {
    "should_appear": false | true,
    "message":       "" | "The patient limit has been reached. A maximum of 10 patients is allowed per number"
  },

  "patient": {
    "salutation":    "Mr. | Mrs. | Master | Miss | Dr.",
    "first_name":    "string",
    "middle_name":   "string | empty string",
    "last_name":     "string",
    "gender":        "Male | Female | empty string (auto-set from salutation)",
    "risk_level":    "Normal | Moderate Risk | High Risk | Emergency",
    "age":           integer,
    "date_of_birth": "DD/MM/YYYY | empty string",
    "mobile_number": "10-digit string",
    "email":         "string | empty string",
    "address": {
      "pincode":      "6-digit string | empty string",
      "address_line": "string | empty string"
    }
  },

  "relative": {
    "relation":      "Wife | Husband | Brother | Sister | Father | Mother | Son | Daughter",
    "salutation":    "Mr. | Mrs. | Master | Miss | Dr.",
    "first_name":    "string",
    "middle_name":   "string | empty string",
    "last_name":     "string",
    "gender":        "Male | Female | empty string",
    "risk_level":    "Normal | Moderate Risk | High Risk | Emergency",
    "age":           integer,
    "email":         "string | empty string",
    "address": {
      "pincode":      "6-digit string | empty string",
      "address_line": "string | empty string"
    }
  }
}
```

> `relative` is an empty object `{}` for non-relative scenarios.

---

### B. Front Desk — Test & Payment Data
**File:** `test_data/front_desk/test_payment_data.json`  
**Root key:** `patient_test_map[]`  
**Lookup:** `patient_id_ref`

```json
{
  "patient_id_ref": "P1",
  "scenario": "Free-text description",

  "tests": [
    {
      "test_name":       "Complete Blood Count (CBC) | CBC Hemogram with ESR | 24 Hrs Urinary Sodium | Electrolytes, Urine | Renal Function test (RFT / KFT), Serum | LFT-Liver Function Test, Serum | 24 Hrs Urinary Potassium",
      "sample":          "Whole Blood/Plasma | Serum | 24-hour urine | Urine",
      "sub_department":  "Hematology | Clinical Chemistry"
    }
  ],

  "payment": {
    "home_collection": integer,
    "cash":            integer,
    "online":          integer
  }
}
```

> `tests` contains 3–7 entries per patient. All 7 test names are shown above.

---

### C. Phlebotomist Actions
**File:** `test_data/phlebotomist/phlebotomist_actions.json`  
**Root key:** `patients[]`  
**Lookup:** `patient_id_ref`

```json
{
  "patient_id_ref": "P1",
  "scenario": "Free-text description",

  "filters": {
    "from_date": "DD/MM/YYYY",
    "to_date":   "DD/MM/YYYY"
  },

  "sample_rules": [
    {
      "sample":          "Whole Blood/Plasma | Serum | 24-hour urine | Urine",
      "sub_department":  "Hematology | Clinical Chemistry",
      "action":          "toggle_on | toggle_off"
    }
  ]
}
```

> `filters` is **optional** — omit to use the global date from `config/test_config.yaml`.

---

### D. Accession Actions
**File:** `test_data/accession/accession_actions.json`  
**Root key:** `patients[]`  
**Lookup:** `patient_id_ref`

```json
{
  "patient_id_ref": "P1",
  "scenario": "Free-text description",

  "filters": {
    "from_date": "DD/MM/YYYY",
    "to_date":   "DD/MM/YYYY"
  },

  "samples": [
    {
      "sample":         "Whole Blood/Plasma | Serum | 24-hour urine | Urine",
      "sub_department": "Hematology | Clinical Chemistry",
      "action":         "accept | reject | refresh",

      "rejection": {
        "sub_department":        "Hematology | Clinical Chemistry",
        "select_random_reasons": integer,
        "reason_text":           "Free-text reason entered in rejection modal"
      }
    }
  ],

  "re_accept": [
    {
      "samples": [
        {
          "sample":         "Whole Blood/Plasma | Serum | 24-hour urine | Urine",
          "sub_department": "Hematology | Clinical Chemistry",
          "action":         "accept",
          "re_accept":      "yes"
        }
      ]
    }
  ]
}
```

> `rejection` is required only when `action` is `"reject"`.  
> `re_accept` is an optional array of recollection phases (one object per cycle).  
> `filters` is optional — omit to inherit global date.

---

### E. Lab Technician Actions
**File:** `test_data/lab_technician/labtech_actions.json`  
**Root key:** `patients[]`  
**Lookup:** `patient_id_ref`

```json
{
  "patient_id_ref": "P1",
  "scenario": "Free-text description",

  "filters": {
    "from_date": "DD/MM/YYYY",
    "to_date":   "DD/MM/YYYY"
  },

  "sample_actions": [
    {
      "sample":         "Whole Blood/Plasma | Serum | 24-hour urine | Urine",
      "sub_department": "Hematology | Clinical Chemistry",
      "action":         "accept | reject | refresh_then_accept",

      "rejection": {
        "sub_department":        "Hematology | Clinical Chemistry",
        "select_random_reasons": integer,
        "reason_text":           "Free-text reason"
      }
    }
  ],

  "tests": [
    {
      "test_name":      "Complete Blood Count (CBC) | CBC Hemogram with ESR | 24 Hrs Urinary Sodium | Electrolytes, Urine | Renal Function test (RFT / KFT), Serum | LFT-Liver Function Test, Serum | 24 Hrs Urinary Potassium",
      "sub_department": "Hematology | Clinical Chemistry",
      "action":         "save | resample",
      "parameters": {
        "<param_name>": "<numeric string value>"
      }
    }
  ],

  "re_cycles": [
    {
      "_note": "Free-text description of this recollection phase",
      "filters": { "from_date": "DD/MM/YYYY", "to_date": "DD/MM/YYYY" },
      "sample_actions": [ ],
      "tests": [ ]
    }
  ]
}
```

**Known parameter names by test:**

| Test | Parameters |
|------|------------|
| Complete Blood Count (CBC) | Haemoglobin, RBC, Total WBC count, Platelet Count, PCV (HCT), MCV, MCH, MCHC |
| CBC Hemogram with ESR | ESR (Westergren Method) |
| Renal Function test (RFT / KFT), Serum | Creatinine, Urea, BUN, Uric Acid, Calcium |
| LFT-Liver Function Test, Serum | Bilirubin - Total, Bilirubin - Direct, SGOT (AST), SGPT (ALT), Alkaline Phosphatase, Total Protein, Albumin |
| 24 Hrs Urinary Sodium | Urine volume in 24 hours, Sodium, Urine |
| 24 Hrs Urinary Potassium | Urine volume in 24 hours, Potassium, Urine |
| Electrolytes, Urine | Sodium, Urine (spot); Potassium, Urine (spot) |

> `rejection` is required only when `action` is `"reject"`.  
> `re_cycles` is optional — include one object per recollection phase.  
> `filters` inside `re_cycles` is also optional.

---

### F. Doctor Actions
**File:** `test_data/doctor/doctor_actions.json`  
**Root key:** `patients[]`  
**Lookup:** `patient_id_ref`

```json
{
  "patient_id_ref": "P1",
  "scenario": "Free-text description",

  "filters": {
    "from_date": "DD/MM/YYYY",
    "to_date":   "DD/MM/YYYY"
  },

  "sub_departments": [
    {
      "sub_dept_name": "Hematology | Clinical Chemistry",
      "tests": [
        {
          "test_name": "Complete Blood Count (CBC) | CBC Hemogram with ESR | ...",
          "action":    "approve | partial_approve | retest | resample | rectify",

          "parameters": {
            "<param_name>": "<numeric string value>"
          },

          "reason": "Free-text reason (required for resample and rectify)",

          "others_text": "Additional notes (used when rectify reason = 'Others')"
        }
      ]
    }
  ],

  "re_approval": {
    "_note": "Free-text description of the re-approval phase",
    "sub_departments": [ ]
  }
}
```

**Doctor action rules:**

| Action | `parameters` | `reason` | `others_text` |
|--------|-------------|----------|---------------|
| `approve` | Required | Not used | Not used |
| `partial_approve` | Required (partial) | Not used | Not used |
| `retest` | Not used | Not used | Not used |
| `resample` | Not used | Required | Optional |
| `rectify` | Optional | Required | Optional (when reason = "Others") |

> `re_approval` is optional — include only when the doctor needs to re-review after a resample cycle.  
> `filters` is optional — omit to inherit global date.
