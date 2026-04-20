"""Lab Technician Report Entry — Regression test (standalone)."""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.test_helpers import smart_parametrize
from flows.labtech_flow import execute_labtech_search, execute_labtech_tests
from state import runtime_state

_ROOT = Path(__file__).resolve().parents[2]
LT_DATA = load_json(_ROOT / "test_data/lab_technician/labtech_actions.json")
PATIENT_IDS = [p["patient_id_ref"] for p in LT_DATA["patients"]]


def _shot(page, pid, label):
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/labtech_{pid}_{label}.png"
    page.screenshot(path=path)
    return path


@pytest.mark.regression
@smart_parametrize("patient_id", PATIENT_IDS)
def test_labtech_report_entry(page, login_as, patient_id):
    """Accept samples and fill test report for each patient scenario."""
    assert runtime_state.get_value("patient_name"), (
        f"[{patient_id}] patient_name not in runtime_state — run front desk first"
    )
    login_as("lab_technician")
    lt_e = next(p for p in LT_DATA["patients"] if p["patient_id_ref"] == patient_id)
    search_r = execute_labtech_search(page, lt_e)
    if search_r["error_found"]:
        pytest.fail(f"[{patient_id}] LT Search: {search_r['error_message']}\n  {_shot(page, patient_id, 'search_error')}")
    assert search_r["completed"]
    tests_r = execute_labtech_tests(page, lt_e)
    if tests_r["error_found"]:
        pytest.fail(f"[{patient_id}] LT Tests: {tests_r['error_message']}\n  {_shot(page, patient_id, 'tests_error')}")
    assert tests_r["completed"]
    for t in tests_r["test_results"]:
        assert t["error"] is None, f"Test error: {t['test_name']} — {t['error']}"
