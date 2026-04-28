"""Lab Technician Report Entry flow orchestrator."""

from typing import Any, Dict, List, Optional
from flows._guard import check_ui_error
from pages.lab_technician.labtech_page import LabTechPage
from state import runtime_state
from utils.date_utils import resolve_filters


def execute_labtech_search(
    page: Any,
    search_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Stage 1 + 2: search, accept samples, open report."""
    lp = LabTechPage(page)
    filters = resolve_filters(search_entry)
    department = search_entry.get("department")
    sub_department = search_entry.get("sub_department")
    sample_actions = search_entry.get("sample_actions", [])

    patient_name = runtime_state.get_value("patient_name")
    patient_mobile = runtime_state.get_value("patient_mobile")
    samples = runtime_state.get_samples()

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
        "action_results": [],
    }

    if not lp.wait_for_report_entry_visible():
        result["error_found"] = True
        result["error_message"] = "Report Entry menu not visible after login"
        return result

    lp.click_report_entry_menu()

    if check_ui_error(page, result, "post-menu"):
        return result

    lp.apply_date_filters(filters["from_date"], filters["to_date"])

    if department:
        lp.select_department(department)
    if sub_department:
        lp.select_sub_department(sub_department)

    lp.fill_search_name(patient_name)
    lp.fill_search_mobile(patient_mobile)
    lp.click_apply_filter()

    if check_ui_error(page, result, "post-search"):
        return result

    if not lp.wait_for_patient_rows():
        result["error_found"] = True
        result["error_message"] = (
            f"No patient rows found for: {patient_name} | {patient_mobile}"
        )
        return result

    for action_rule in sample_actions:
        action_entry = _process_sample_action(lp, action_rule, samples)
        result["action_results"].append(action_entry)

        if action_entry.get("error"):
            result["error_found"] = True
            result["error_message"] = action_entry["error"]
            return result

    # Use first sample ID to open the correct row when multiple same-day registrations exist
    anchor_id = samples[0]["id"] if samples else None
    if not lp.open_report_entry(sample_id=anchor_id):
        result["error_found"] = True
        result["error_message"] = "Report Entry icon not found after 10 scroll attempts"
        return result

    if check_ui_error(page, result, "end-of-flow"):
        return result

    result["completed"] = True
    return result


def execute_labtech_tests(
    page: Any,
    tests_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute Stage 3: process all tests for a patient."""
    lp = LabTechPage(page)
    tests = tests_entry["tests"]

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
        "test_results": [],
    }

    for test in tests:
        test_result = _process_single_test(lp, test)
        result["test_results"].append(test_result)

        if test_result.get("error"):
            result["error_found"] = True
            result["error_message"] = test_result["error"]
            return result

    if check_ui_error(page, result, "end-of-flow"):
        return result

    result["completed"] = True
    return result


_ACTION_TEXT_MAP = {
    "accept": "Accept",
    "reject": "Reject",
    "refresh": "Refresh",
    "refresh_then_accept": "Refresh",  # resampled: Refresh first, then Accept
}


def _process_sample_action(
    lp: LabTechPage,
    rule: Dict[str, Any],
    samples: List[Dict],
) -> Dict[str, Any]:
    """Process a single sample action: match → find block → execute."""
    entry: Dict[str, Any] = {
        "sample": rule["sample"],
        "sub_department": rule["sub_department"],
        "action": rule["action"],
        "sample_id": None,
        "result": None,
        "error": None,
    }

    action = rule["action"]
    action_text = _ACTION_TEXT_MAP.get(action, "")
    anchor_id = samples[0]["id"] if samples else None

    matched = _match_runtime_sample(samples, rule["sample"], rule["sub_department"])
    sub_row = None

    if matched:
        sample_id = matched["id"]
        entry["sample_id"] = sample_id
        candidate = lp.find_sample_sub_row(rule["sample"], sample_id)
        # Guard against stale IDs: after recollection old Serum shows Refresh not Accept
        if candidate and (not action_text or action_text in candidate.inner_text()):
            sub_row = candidate

    if sub_row is None:
        if action_text:
            sub_row = lp.find_sample_sub_row_by_action(
                rule["sample"], action_text, anchor_id=anchor_id
            )
        else:
            sub_row = lp.find_sample_sub_row_by_name(
                rule["sample"], anchor_id=anchor_id
            )

    if not sub_row:
        entry["error"] = (
            f"Sample sub-row not found: {rule['sample']} | {rule['sub_department']}"
        )
        return entry

    action = rule["action"]

    if action == "accept":
        lp.click_accept_sample(sub_row)
        entry["result"] = "accepted"

    elif action == "refresh":
        lp.click_refresh_sample(sub_row)
        entry["result"] = "refreshed"

    elif action == "refresh_then_accept":
        lp.click_refresh_sample(sub_row)
        lp.wait_for_idle(2.5)
        # Re-find after Refresh — should now show Accept
        accept_row = lp.find_sample_sub_row_by_action(
            rule["sample"], "Accept", anchor_id=samples[0]["id"] if samples else None
        )
        if accept_row:
            lp.click_accept_sample(accept_row)
            entry["result"] = "refreshed_then_accepted"
        else:
            entry["error"] = (
                f"Accept button not found after Refresh for: {rule['sample']}"
            )
            return entry

    elif action == "reject":
        lp.click_reject_sample(sub_row)
        rejection_config = rule.get("rejection", {})
        handled = lp.handle_rejection_modal(rejection_config)
        if not handled:
            entry["error"] = "Rejection modal did not appear or failed"
            return entry
        entry["result"] = "rejected"

    return entry


def _process_single_test(
    lp: LabTechPage,
    test: Dict[str, Any],
) -> Dict[str, Any]:
    """Process a single test: traverse → fill/resample → save."""
    test_name = test["test_name"]
    action = test["action"]

    entry: Dict[str, Any] = {
        "test_name": test_name,
        "sub_department": test.get("sub_department"),
        "action": action,
        "result": None,
        "error": None,
    }

    row = lp.traverse_and_find_test(test_name)
    if not row:
        entry["error"] = f"Test not found in any sub-department: {test_name}"
        return entry

    if action == "save":
        entry = _handle_save(lp, row, test, entry)
    elif action == "resample":
        entry = _handle_resample(lp, row, test, entry)

    return entry


def _handle_save(
    lp: LabTechPage,
    row: Any,
    test: Dict[str, Any],
    entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Fill all parameters and click Save."""
    test_name = test["test_name"]
    parameters = test.get("parameters", {})

    for param_name, value in parameters.items():
        filled = lp.fill_parameter(row, param_name, value)
        if not filled:
            entry["error"] = (
                f"Parameter fill failed: {test_name} → {param_name}"
            )
            return entry

    saved = lp.save_test(row)
    if not saved:
        entry["error"] = f"Save failed or disabled: {test_name}"
        return entry

    entry["result"] = "saved"
    return entry


def _handle_resample(
    lp: LabTechPage,
    row: Any,
    test: Dict[str, Any],
    entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Click Re-sample, fill reason, and submit."""
    test_name = test["test_name"]
    reason = test.get("resample_reason", "")

    resampled = lp.resample_test(row, reason)
    if not resampled:
        entry["error"] = f"Resample failed: {test_name}"
        return entry

    entry["result"] = "resampled"
    return entry


def _match_runtime_sample(
    samples: List[Dict], sample_name: str, sub_department: str
) -> Optional[Dict]:
    """Match a DDT sample rule against runtime_state samples."""
    for s in samples:
        if s["name"] == sample_name and s["sub_department"] == sub_department:
            return s
    return None
