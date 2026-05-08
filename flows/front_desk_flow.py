"""Front Desk registration flow orchestrator."""

from typing import Any, Dict
from flows._guard import check_ui_error
from pages.front_desk.front_desk_page import FrontDeskPage
from state import runtime_state

# Salutations where the UI auto-selects gender (do NOT click gender radio)
SALUTATION_AUTO_GENDER: Dict[str, str] = {
    "Mr": "Male",
    "Mr.": "Male",
    "Master": "Male",
    "Mrs": "Female",
    "Mrs.": "Female",
    "Miss": "Female",
    "Miss.": "Female",
}


def execute_front_desk_registration(
    page: Any,
    patient_entry: Dict[str, Any],
    test_payment_entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute the full front desk patient registration flow."""
    fd = FrontDeskPage(page)
    intent = patient_entry["patient_intent"]
    patient = patient_entry["patient"]
    relative = patient_entry.get("relative", {})

    expected_err = patient_entry.get("expected_error", {})

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "expected_error_matched": False,
        "completed": False,
        "patient_display_name": "",
    }

    # new_relative fills from `relative`; all others fill from `patient`
    is_new_relative = intent["relative_action"] == "add_new"
    is_adding_new_relative = (
        intent["relative_action"] == "add_new_relative"
        and not intent.get("card_display_name")
        and bool(relative)
    )
    is_existing = intent["patient_type"] in (
        "existing_primary", "existing_relative",
    )
    form_data = relative if (is_new_relative or is_adding_new_relative) else patient

    # For relative-patient scenarios, the registered patient IS the relative —
    # build display_name from relative so downstream searches use the correct name.
    is_relative_case = intent["relative_action"] in ("add_new", "add_new_relative", "select_existing_relative") and bool(relative)
    display_name = _build_display_name(relative if is_relative_case else patient)
    result["patient_display_name"] = display_name
    runtime_state.set_value("mobile_number", patient["mobile_number"])

    fd.click_add_patient()

    risk_level = form_data.get("risk_level", "")
    if risk_level:
        fd.select_risk_level(risk_level)

    if intent["search_before_add"]:
        fd.search_mobile(patient["mobile_number"])
        fd.click_search()

        error = fd.detect_error()
        if error:
            return _set_error(result, error, expected_err)

        # Decide which card (if any) to click on the search-results page.
        # The primary patient should ONLY be clicked for vanilla
        # existing-primary flows. Relative flows go a different way:
        #   * select_existing_relative → click the relative's card directly.
        #   * add_new / add_new_relative → click "Add Relative" instead
        #     (no primary click). When card_display_name is set on an
        #     "add_*" flow, the relative already exists from a prior run, so
        #     we click that card directly (idempotent shortcut).
        relative_action = intent["relative_action"]
        if is_existing:
            if relative_action == "select_existing_relative":
                card_name = intent.get("card_display_name") or _build_card_name(relative)
                fd.select_patient_card(card_name)
            elif relative_action in ("add_new", "add_new_relative"):
                if intent.get("card_display_name"):
                    fd.select_patient_card(intent["card_display_name"])
                # otherwise fall through to click_add_relative below — no primary click.
            else:
                # relative_action == "none" → existing primary patient
                card_name = intent.get("card_display_name") or _build_card_name(patient)
                fd.select_patient_card(card_name)

        if relative_action in ("add_new", "add_new_relative") and not intent.get("card_display_name"):
            fd.click_add_relative()

            # "10 patients limit" toast appears here, not after search
            error = fd.detect_error()
            if error:
                return _set_error(result, error, expected_err)

            if relative.get("relation"):
                fd.select_relation(relative["relation"])
            elif expected_err.get("should_appear"):
                # Expected an error toast (e.g. P7's 10-patient limit) that
                # didn't appear — likely a parallel state race on the mobile.
                # Fail with the expected-error context instead of cascading
                # into "Please select relation" via an empty form submit.
                result["error_found"] = True
                result["error_message"] = (
                    f"Expected error '{expected_err.get('message')}' did not "
                    f"appear after click_add_relative; cannot proceed without "
                    f"relation data."
                )
                return result

    if intent["search_before_add"]:
        auto_filled_mobile = fd.get_mobile_value()
        runtime_state.set_value("mobile_auto_filled", auto_filled_mobile)

    if is_existing and not is_new_relative and not is_adding_new_relative:
        # Existing patient — fields prefilled from selected card, skip to Next
        pass
    else:
        fd.select_salutation(form_data["salutation"])
        auto_gender = SALUTATION_AUTO_GENDER.get(form_data["salutation"])
        if auto_gender:
            runtime_state.set_value("expected_auto_gender", auto_gender)
        elif form_data.get("gender"):
            fd.select_gender(form_data["gender"])

        fd.fill_patient_name(
            form_data["first_name"],
            form_data.get("middle_name", ""),
            form_data["last_name"],
        )
        fd.fill_age(str(form_data["age"]))

        if is_new_relative or is_adding_new_relative:
            # Mobile & address are prefilled from primary — only fill if empty
            fd.fill_pin_code_if_empty(form_data["address"]["pincode"])
            fd.fill_address_if_empty(form_data["address"]["address_line"])
            if form_data.get("email"):
                fd.fill_email_if_empty(form_data["email"])
            fd.fill_mobile_if_empty(patient["mobile_number"])
        else:
            fd.fill_pin_code(form_data["address"]["pincode"])
            fd.fill_address(form_data["address"]["address_line"])
            if form_data.get("email"):
                fd.fill_email(form_data["email"])
            fd.fill_mobile(form_data["mobile_number"])

    if intent["patient_type"] == "new_user":
        error = fd.detect_error()
        if error:
            return _set_error(result, error, expected_err)

    fd.click_next()

    # Catch post-Next errors (e.g. P11: "Patient record(s) found with the given mobile number")
    error = fd.detect_error()
    if error:
        return _set_error(result, error, expected_err)

    tests = test_payment_entry["tests"]
    for test in tests:
        fd.add_test(test["test_name"])

    payment = test_payment_entry["payment"]
    fd.fill_payments(
        str(payment["home_collection"]),
        str(payment["cash"]),
        str(payment["online"]),
    )

    balance = fd.get_balance()
    runtime_state.set_value("balance", balance)

    fd.click_submit()

    error = fd.detect_error()
    if error:
        return _set_error(result, error, expected_err)

    # Let the post-submit modal finish wiring up before triggering the
    # popup-bound Print Bill click. Without this, the popup-page event
    # occasionally fires before its listener attaches under worksteal load.
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    fd.wait_for_idle(1)

    fd.click_print_bill()
    fd.click_print_barcode()

    samples = fd.capture_samples(tests)
    for sample in samples:
        runtime_state.add_sample(
            sample["name"], sample["sub_department"],
            sample["id"], sample["index"],
        )

    fd.close_barcode_modals()

    # End-of-flow guard: catches any toast that fires after barcode capture
    # (e.g. backend validation that surfaces only post-Submit).
    if check_ui_error(page, result, "post-submit-final", expected_err):
        return result

    runtime_state.set_value("patient_name", display_name)
    runtime_state.set_value("patient_mobile", patient["mobile_number"])
    runtime_state.set_value("mobile_number", patient["mobile_number"])
    runtime_state.set_value("patient_id_ref", patient_entry["patient_id_ref"])
    runtime_state.set_value("patient_id", patient_entry["patient_id_ref"])

    result["completed"] = True
    return result


def execute_front_desk_published_reports(
    page: Any,
    patient_name: str,
) -> Dict[str, Any]:
    """Navigate to Published Reports and verify the patient report is visible."""
    fd = FrontDeskPage(page)

    result: Dict[str, Any] = {
        "error_found": False,
        "error_message": None,
        "completed": False,
    }

    fd.navigate_to_published_reports()

    row = fd.find_published_report(patient_name)
    if not row:
        result["error_found"] = True
        result["error_message"] = f"Published report not found for: {patient_name}"
        return result

    result["completed"] = True
    return result


def _build_display_name(data: Dict[str, Any]) -> str:
    """Build 'First Middle Last' display name from patient or relative dict."""
    parts = [
        data.get("first_name", ""),
        data.get("middle_name", ""),
        data.get("last_name", ""),
    ]
    return " ".join(p for p in parts if p).strip()


def _set_error(
    result: Dict[str, Any],
    error: str,
    expected_err: Dict[str, Any],
) -> Dict[str, Any]:
    """Populate error fields; flag expected_error_matched when the error was anticipated."""
    result["error_found"] = True
    result["error_message"] = error
    if expected_err.get("should_appear") and expected_err.get("message", "") in error:
        result["expected_error_matched"] = True
    return result


def _build_card_name(patient: Dict[str, str]) -> str:
    """Build 'First Middle' name for patient card selection."""
    parts = [
        patient.get("first_name", ""),
        patient.get("middle_name", ""),
    ]
    return " ".join(p for p in parts if p).strip()
