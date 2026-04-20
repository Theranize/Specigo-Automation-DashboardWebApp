"""Doctor Report Review — Regression test (standalone).

Runs the doctor flow for each patient in doctor_actions.json.
Requires runtime_state to already contain patient_name and patient_mobile
(set by a prior front desk registration).

Use this test to regression-test the doctor review phase independently
after the full pipeline has already produced processed test results.

DDT file: test_data/doctor/doctor_actions.json
"""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.test_helpers import smart_parametrize
from flows.doctor_flow import execute_doctor_flow
from state import runtime_state

# ── Resolve paths ─────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOCTOR_DATA = load_json(_PROJECT_ROOT / "test_data/doctor/doctor_actions.json")
PATIENT_IDS = [p["patient_id_ref"] for p in DOCTOR_DATA["patients"]]


def _get_patient_entry(patient_id: str) -> dict:
    """Look up doctor patient entry by patient_id_ref."""
    return next(
        p for p in DOCTOR_DATA["patients"]
        if p["patient_id_ref"] == patient_id
    )


def _take_screenshot(page, patient_id: str, label: str) -> str:
    """Capture screenshot and return path."""
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/doctor_{patient_id}_{label}.png"
    page.screenshot(path=path)
    return path


def _print_test_results(patient_id: str, test_results: list) -> None:
    """Print doctor test results in a formatted table."""
    print(f"\n{'=' * 75}")
    print(f"[{patient_id}] DOCTOR — REPORT REVIEW RESULTS")
    print(f"{'Test Name':<45} | {'Action':<15} | {'Result'}")
    print(f"{'-' * 75}")
    for t in test_results:
        result_val = t.get("result") or f"ERROR: {t.get('error')}"
        print(f"{t['test_name']:<45} | {t['action']:<15} | {result_val}")
    print(f"{'=' * 75}")


@pytest.mark.regression
@smart_parametrize("patient_id", PATIENT_IDS)
def test_doctor_report_review(page, login_as, patient_id):
    """Execute doctor report review for a single patient scenario.

    Verifies:
      - patient_name and patient_mobile present in runtime_state
      - Report Entry navigates and filters correctly
      - All tests in each sub-department are actioned without error
      - Every test result is non-None (i.e., action was completed)
    """
    # ── Verify runtime identity ────────────────────────────
    patient_name = runtime_state.get_value("patient_name")
    patient_mobile = runtime_state.get_value("patient_mobile")

    assert patient_name, (
        f"[{patient_id}] runtime_state.patient_name is empty — "
        "run front desk registration first"
    )
    assert patient_mobile, (
        f"[{patient_id}] runtime_state.patient_mobile is empty — "
        "run front desk registration first"
    )

    # ── Login as Doctor ────────────────────────────────────
    login_as("doctor")

    patient_entry = _get_patient_entry(patient_id)

    result = execute_doctor_flow(page, patient_entry)

    # ── Error path ─────────────────────────────────────────
    if result["error_found"]:
        screenshot = _take_screenshot(page, patient_id, "error")
        pytest.fail(
            f"[{patient_id}] Doctor flow error: {result['error_message']}\n"
            f"  Screenshot: {screenshot}"
        )

    assert result["completed"], f"[{patient_id}] Doctor flow did not complete"

    # ── Print results ──────────────────────────────────────
    _print_test_results(patient_id, result["test_results"])

    # ── Per-test assertions ────────────────────────────────
    for t in result["test_results"]:
        assert t["error"] is None, (
            f"[{patient_id}] Test error: {t['test_name']} — {t['error']}"
        )
        assert t["result"] is not None, (
            f"[{patient_id}] Test result not set: {t['test_name']}"
        )
