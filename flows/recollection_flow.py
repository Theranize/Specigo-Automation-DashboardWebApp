"""Phlebotomist Re-Collection flow orchestrator."""

from typing import Any, Dict
from flows._guard import check_ui_error
from pages.phlebotomist.recollection_page import RecollectionPage
from state import runtime_state
from utils.date_utils import resolve_filters


def execute_recollection_flow(
    page: Any,
    recollection_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the phlebotomist Re-Collection tab toggle flow."""
    rp = RecollectionPage(page)
    filters = resolve_filters(recollection_entry)
    samples = recollection_entry["samples"]

    patient_name = runtime_state.get_value("patient_name")
    mobile_number = runtime_state.get_value("mobile_number")

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
        "toggle_results": [],
    }

    rp.navigate_to_sample_tracker()

    if not rp.verify_page_header():
        result["error_found"] = True
        result["error_message"] = "Page header verification failed"
        return result

    rp.switch_to_recollection_tab()
    rp.apply_date_filters(filters["from_date"], filters["to_date"])
    rp.fill_search_name(patient_name)
    rp.fill_search_mobile(mobile_number)
    rp.click_search()

    if check_ui_error(page, result, "post-search"):
        return result

    if not rp.wait_for_rows():
        result["error_found"] = True
        result["error_message"] = (
            f"No rows found in Re-Collection tab for: "
            f"{patient_name} | {mobile_number}"
        )
        return result

    for rule in samples:
        entry: Dict[str, Any] = {
            "sub_department": rule["sub_department"],
            "sample_name": rule["sample_name"],
            "action": rule["action"],
            "result": None,
            "error": None,
        }

        block = rp.find_sample_block(
            patient_name, rule["sub_department"], rule["sample_name"]
        )
        if not block:
            entry["error"] = (
                f"Sample block not found: "
                f"{rule['sub_department']} | {rule['sample_name']}"
            )
            result["error_found"] = True
            result["error_message"] = entry["error"]
            result["toggle_results"].append(entry)
            return result

        toggle_result = rp.toggle_sample(block, rule["action"])
        entry["result"] = toggle_result

        if check_ui_error(page, result, "post-toggle"):
            result["toggle_results"].append(entry)
            return result

        # Store new sample ID so accession can re-accept by ID
        if toggle_result in ("toggled_on", "already_on"):
            new_id = rp.get_block_sample_id(block)
            if new_id:
                state_key = f"new_id::{rule['sample_name']}::{rule['sub_department']}"
                runtime_state.set_value(state_key, new_id)
                entry["new_sample_id"] = new_id

        result["toggle_results"].append(entry)

    if check_ui_error(page, result, "end-of-flow"):
        return result

    result["completed"] = True
    return result
