"""Phlebotomist Sample Toggle flow orchestrator."""

from typing import Any, Dict, List, Optional
from pages.phlebotomist.phlebotomist_page import PhlebotomistPage
from state import runtime_state
from utils.date_utils import resolve_filters


def execute_phlebotomist_flow(
    page: Any,
    phlebo_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the phlebotomist sample toggle flow."""
    pp = PhlebotomistPage(page)
    filters = resolve_filters(phlebo_entry)
    sample_rules = phlebo_entry["sample_rules"]

    patient_name = runtime_state.get_value("patient_name")
    patient_mobile = runtime_state.get_value("patient_mobile")
    samples = runtime_state.get_samples()

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
        "toggle_results": [],
    }

    pp.navigate_to_sample_tracker()

    if not pp.verify_page_header():
        result["error_found"] = True
        result["error_message"] = "Page header verification failed"
        return result

    pp.apply_date_filters(filters["from_date"], filters["to_date"])
    pp.fill_search_name(patient_name)
    pp.fill_search_mobile(patient_mobile)

    for rule in sample_rules:
        matched_sample = _match_runtime_sample(
            samples, rule["sample"], rule["sub_department"]
        )
        if not matched_sample:
            result["error_found"] = True
            result["error_message"] = (
                f"No runtime match: {rule['sample']} | {rule['sub_department']}"
            )
            return result

        sample_id = matched_sample["id"]
        pp.fill_search_id(sample_id)
        pp.click_search()

        block = pp.find_sample_block(rule["sample"], sample_id)
        if not block:
            result["error_found"] = True
            result["error_message"] = (
                f"Sample block not found in UI: "
                f"{rule['sample']} | {sample_id}"
            )
            return result

        toggle_result = pp.toggle_sample(block, rule["action"])
        result["toggle_results"].append({
            "sample": rule["sample"],
            "sub_department": rule["sub_department"],
            "sample_id": sample_id,
            "action": rule["action"],
            "result": toggle_result,
        })

    result["completed"] = True
    return result


def _match_runtime_sample(
    samples: List[Dict], sample_name: str, sub_department: str
) -> Optional[Dict]:
    """Match a DDT sample rule against runtime_state samples."""
    for s in samples:
        if s["name"] == sample_name and s["sub_department"] == sub_department:
            return s
    return None
