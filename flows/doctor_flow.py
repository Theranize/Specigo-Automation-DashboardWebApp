"""Doctor Report Review flow orchestrator."""

from typing import Any, Dict, List
from pages.doctor.doctor_page import DoctorPage
from state import runtime_state
from utils.date_utils import resolve_filters


def execute_doctor_flow(
    page: Any,
    patient_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the full Doctor Report Review flow for one patient."""
    dp = DoctorPage(page)

    filters = resolve_filters(patient_entry)
    sub_departments = patient_entry["sub_departments"]

    patient_name = runtime_state.get_value("patient_name")
    patient_mobile = runtime_state.get_value("patient_mobile")
    samples = runtime_state.get_samples()

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
        "test_results": [],
    }

    if not dp.wait_for_report_entry_visible():
        result["error_found"] = True
        result["error_message"] = "Report Entry menu not visible after login"
        return result

    dp.click_report_entry_menu()
    dp.apply_date_filters(filters["from_date"], filters["to_date"])
    dp.fill_search_name(patient_name)
    dp.fill_search_mobile(patient_mobile)
    dp.click_apply_filter()

    if not dp.wait_for_patient_rows():
        result["error_found"] = True
        result["error_message"] = (
            f"No patient rows found for: {patient_name} | {patient_mobile}"
        )
        return result

    anchor_id = samples[0]["id"] if samples else None
    if not dp.open_report_entry(sample_id=anchor_id):
        result["error_found"] = True
        result["error_message"] = "Report Entry icon not found after hover attempts"
        return result

    for sub_dept in sub_departments:
        sub_result = _process_sub_department(dp, sub_dept)
        result["test_results"].extend(sub_result["test_results"])

        if sub_result["error_found"]:
            result["error_found"] = True
            result["error_message"] = sub_result["error_message"]
            return result

    result["completed"] = True
    return result


def _process_sub_department(
    dp: DoctorPage,
    sub_dept: Dict[str, Any],
) -> Dict[str, Any]:
    """Navigate to a sub-department and process all its tests."""
    sub_result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "test_results": [],
    }

    sub_dept_name = sub_dept["sub_dept_name"]

    if not dp.navigate_to_sub_dept(sub_dept_name):
        sub_result["error_found"] = True
        sub_result["error_message"] = (
            f"Sub-department not found after 20 navigation attempts: {sub_dept_name}"
        )
        return sub_result

    for test in sub_dept["tests"]:
        test_result = _process_single_test(dp, test)
        sub_result["test_results"].append(test_result)

        if test_result.get("error"):
            sub_result["error_found"] = True
            sub_result["error_message"] = test_result["error"]
            return sub_result

    return sub_result


def _process_single_test(
    dp: DoctorPage,
    test: Dict[str, Any],
) -> Dict[str, Any]:
    """Find the test row and dispatch to the appropriate action handler."""
    test_name = test["test_name"]
    action = test["action"]

    entry: Dict[str, Any] = {
        "test_name": test_name,
        "action": action,
        "result": None,
        "error": None,
    }

    row = dp.find_test_row(test_name)
    if not row:
        entry["error"] = f"Test row not found: {test_name}"
        return entry

    if action == "retest":
        entry = _handle_retest(dp, row, test, entry)

    elif action == "resample":
        entry = _handle_resample(dp, row, test, entry)

    elif action in ("approve", "partial_approve"):
        entry = _handle_approve(dp, row, test, entry, action)

    elif action == "rectify":
        entry = _handle_rectify(dp, row, test, entry)

    else:
        entry["error"] = f"Unknown action: {action}"

    return entry


def _handle_retest(
    dp: DoctorPage,
    row: Any,
    test: Dict[str, Any],
    entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Click Re-Test and confirm Yes."""
    if not dp.handle_retest(row):
        entry["error"] = f"Re-Test failed or confirmation missing: {test['test_name']}"
        return entry
    entry["result"] = "retest_submitted"
    return entry


def _handle_resample(
    dp: DoctorPage,
    row: Any,
    test: Dict[str, Any],
    entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Click Re-sample, fill reason, and submit."""
    reason = test.get("reason", "")
    if not dp.handle_resample(row, reason):
        entry["error"] = f"Resample failed or dialog missing: {test['test_name']}"
        return entry
    entry["result"] = "resampled"
    return entry


def _handle_approve(
    dp: DoctorPage,
    row: Any,
    test: Dict[str, Any],
    entry: Dict[str, Any],
    action: str,
) -> Dict[str, Any]:
    """Fill parameters (if any), save, then approve fully or partially."""
    test_name = test["test_name"]
    parameters = test.get("parameters", {})

    if parameters:
        fill_error = dp.fill_parameters(row, parameters)
        if fill_error:
            entry["error"] = f"{test_name} → {fill_error}"
            return entry

        if not dp.save_test(row):
            entry["error"] = f"Save failed or disabled: {test_name}"
            return entry

    if not dp.handle_approve(row, action):
        entry["error"] = f"Approve failed or dialog missing: {test_name}"
        return entry

    result_label = "fully_approved" if action == "approve" else "partially_approved"
    entry["result"] = result_label
    return entry


def _handle_rectify(
    dp: DoctorPage,
    row: Any,
    test: Dict[str, Any],
    entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Fill parameters (if any), then click Rectify → select reason → Submit → Yes."""
    test_name = test["test_name"]
    parameters = test.get("parameters", {})
    rectification = test.get("rectification", {})

    if parameters:
        fill_error = dp.fill_parameters(row, parameters)
        if fill_error:
            entry["error"] = f"{test_name} → {fill_error}"
            return entry

    if not dp.handle_rectify(row, rectification):
        entry["error"] = f"Rectify failed or dialog missing: {test_name}"
        return entry

    entry["result"] = "rectified"
    return entry
