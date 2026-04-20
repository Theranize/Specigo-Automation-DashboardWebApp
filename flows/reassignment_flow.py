"""Re-Assignment Log flow orchestrator."""

from typing import Any, Dict
from pages.accession.reassignment_page import ReassignmentPage
from state import runtime_state


def execute_reassignment_flow(
    page: Any,
    reassignment_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Assign rejected samples back to phlebotomist via Re-Assignment Log."""
    rp = ReassignmentPage(page)
    ddt_samples = reassignment_entry.get("samples", [])

    patient_name = runtime_state.get_value("patient_name")
    mobile_number = runtime_state.get_value("mobile_number")

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
        "action_results": [],
    }

    rp.navigate_to_reassignment_log()
    rp.fill_search_filters(patient_name, mobile_number)
    rp.click_search()

    if not rp.wait_for_rows():
        result["error_found"] = True
        result["error_message"] = (
            f"No reassignment rows found for: {patient_name} | {mobile_number}"
        )
        return result

    for rule in ddt_samples:
        entry: Dict[str, Any] = {
            "sample_name": rule["sample_name"],
            "sub_department": rule["sub_department"],
            "note": rule.get("note", ""),
            "result": None,
            "error": None,
        }

        row = rp.find_row(rule["sample_name"])
        if not row:
            entry["error"] = f"Row not found: {rule['sample_name']}"
            result["error_found"] = True
            result["error_message"] = entry["error"]
            result["action_results"].append(entry)
            return result

        ok = rp.assign_sample(row, rule.get("note", ""))
        if not ok:
            entry["error"] = f"Assign failed: {rule['sample_name']}"
            result["error_found"] = True
            result["error_message"] = entry["error"]
            result["action_results"].append(entry)
            return result

        entry["result"] = "assigned"
        result["action_results"].append(entry)

    result["completed"] = True
    return result
