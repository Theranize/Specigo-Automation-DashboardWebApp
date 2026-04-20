"""Phlebotomist Sample Tracker — Regression test (standalone)."""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.test_helpers import smart_parametrize
from flows.phlebotomist_flow import execute_phlebotomist_flow
from state import runtime_state

_ROOT = Path(__file__).resolve().parents[2]
PHLEBO_DATA = load_json(_ROOT / "test_data/phlebotomist/phlebotomist_actions.json")
PATIENT_IDS = [p["patient_id_ref"] for p in PHLEBO_DATA["patients"]]


def _shot(page, pid, label):
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/phlebo_{pid}_{label}.png"
    page.screenshot(path=path)
    return path


@pytest.mark.regression
@smart_parametrize("patient_id", PATIENT_IDS)
def test_phlebotomist_sample_toggle(page, login_as, patient_id):
    """Toggle samples on/off for each patient scenario."""
    assert runtime_state.get_value("patient_name"), (
        f"[{patient_id}] patient_name not in runtime_state — run front desk first"
    )
    login_as("phlebotomist")
    entry = next(p for p in PHLEBO_DATA["patients"] if p["patient_id_ref"] == patient_id)
    result = execute_phlebotomist_flow(page, entry)
    if result["error_found"]:
        pytest.fail(f"[{patient_id}] {result['error_message']}\n  {_shot(page, patient_id, 'error')}")
    assert result["completed"], f"[{patient_id}] Phlebotomist flow did not complete"
    for t in result["toggle_results"]:
        assert t.get("result") is not None, f"Toggle result not set: {t['sample']}"
