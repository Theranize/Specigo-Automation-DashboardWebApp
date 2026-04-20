"""Accession Sample Verification flow orchestrator."""

from typing import Any, Dict, List, Optional
from pages.accession.accession_page import AccessionPage
from state import runtime_state
from utils.date_utils import resolve_filters


def execute_accession_flow(
    page: Any,
    accession_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the accession sample verification flow."""
    ap = AccessionPage(page)
    filters = resolve_filters(accession_entry)
    sample_rules = accession_entry["samples"]

    patient_name = runtime_state.get_value("patient_name")
    patient_mobile = runtime_state.get_value("patient_mobile")
    samples = runtime_state.get_samples()

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
        "action_results": [],
    }

    ap.navigate_to_sample_verification()

    if not ap.wait_for_table_rows():
        result["error_found"] = True
        result["error_message"] = "Table rows not visible after navigation"
        return result

    ap.apply_date_filters(filters["from_date"], filters["to_date"])
    ap.fill_search_name(patient_name)
    ap.fill_search_mobile(patient_mobile)
    ap.click_search()

    for rule in sample_rules:
        action_entry = _process_sample_rule(ap, rule, samples)
        result["action_results"].append(action_entry)

        if action_entry.get("error"):
            result["error_found"] = True
            result["error_message"] = action_entry["error"]
            return result

    result["completed"] = True
    return result


def _process_sample_rule(
    ap: AccessionPage,
    rule: Dict[str, Any],
    samples: List[Dict],
) -> Dict[str, Any]:
    """Process a single sample rule: match → find block → execute action."""
    entry: Dict[str, Any] = {
        "sample": rule["sample"],
        "sub_department": rule["sub_department"],
        "action": rule["action"],
        "sample_id": None,
        "result": None,
        "error": None,
    }

    re_accept = rule.get("re_accept", "").lower()

    # re_accept="no" skips the sample; "yes" uses new ID from recollection
    if re_accept == "no":
        entry["result"] = "skipped"
        return entry

    if re_accept == "yes":
        state_key = f"new_id::{rule['sample']}::{rule['sub_department']}"
        new_id = runtime_state.get_value(state_key)

        if new_id:
            block = ap.find_sample_block(rule["sample"], new_id)
            if not block:
                block = ap.find_sample_block_by_name(rule["sample"])  # fallback
        else:
            block = ap.find_sample_block_by_name(rule["sample"])

        if not block:
            entry["error"] = (
                f"Re-accept block not found: {rule['sample']} | {rule['sub_department']}"
            )
            return entry
        ap.click_accept(block)
        entry["result"] = "re_accepted"
        return entry

    matched = _match_runtime_sample(
        samples, rule["sample"], rule["sub_department"]
    )
    if not matched:
        entry["error"] = (
            f"No runtime match: {rule['sample']} | {rule['sub_department']}"
        )
        return entry

    sample_id = matched["id"]
    entry["sample_id"] = sample_id

    block = ap.find_sample_block(rule["sample"], sample_id)
    if not block:
        entry["error"] = (
            f"Sample block not found in UI: {rule['sample']} | {sample_id}"
        )
        return entry

    action = rule["action"]

    if action == "refresh":
        ap.click_refresh(block)
        entry["result"] = "refreshed"

    elif action == "accept":
        ap.click_accept(block)
        entry["result"] = "accepted"

    elif action == "reject":
        ap.click_reject(block)

        modal = ap.wait_for_rejection_modal()
        if not modal:
            entry["error"] = "Rejection modal did not appear"
            return entry

        rejection_config = rule["rejection"]
        closed = ap.handle_rejection_modal(modal, rejection_config)
        if not closed:
            entry["error"] = "Rejection modal did not close after Send"
            return entry

        entry["result"] = "rejected"

    return entry


def _match_runtime_sample(
    samples: List[Dict], sample_name: str, sub_department: str
) -> Optional[Dict]:
    """Match a DDT sample rule against runtime_state samples."""
    for s in samples:
        if s["name"] == sample_name and s["sub_department"] == sub_department:
            return s
    return None
