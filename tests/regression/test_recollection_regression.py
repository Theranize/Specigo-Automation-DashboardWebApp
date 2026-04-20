"""Phlebotomist Re-Collection — Regression test (standalone).

Prerequisite: runtime_state must have patient_name and mobile_number
set by a prior FD registration or E2E phase.
"""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.test_helpers import smart_parametrize
from flows.recollection_flow import execute_recollection_flow
from state import runtime_state

_ROOT = Path(__file__).resolve().parents[2]
RECOLLECTION_DATA = load_json(
    _ROOT / "test_data/phlebotomist/recollection_actions.json"
)
PATIENT_IDS = [p["patient_id_ref"] for p in RECOLLECTION_DATA["patients"]]


def _shot(page, pid, label):
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/recollection_{pid}_{label}.png"
    page.screenshot(path=path)
    return path


@pytest.mark.regression
@smart_parametrize("patient_id", PATIENT_IDS)
def test_phlebotomist_recollection(page, login_as, patient_id=None):
    """Toggle Re-Collection samples for a rejected patient."""
    assert runtime_state.get_value("patient_name"), (
        f"[{patient_id}] patient_name not in runtime_state — "
        "run front desk registration first"
    )
    assert runtime_state.get_value("mobile_number"), (
        f"[{patient_id}] mobile_number not in runtime_state — "
        "run front desk registration first"
    )

    patient_id = patient_id or PATIENT_IDS[0]
    login_as("phlebotomist")

    entry = next(
        p for p in RECOLLECTION_DATA["patients"]
        if p["patient_id_ref"] == patient_id
    )
    result = execute_recollection_flow(page, entry["cycles"][0])

    if result["error_found"]:
        pytest.fail(
            f"[{patient_id}] {result['error_message']}\n"
            f"  {_shot(page, patient_id, 'error')}"
        )

    assert result["completed"], f"[{patient_id}] Recollection flow did not complete"

    print(f"\n[{patient_id}] RE-COLLECTION — TOGGLE RESULTS")
    for t in result["toggle_results"]:
        print(
            f"  {t['sub_department']} | {t['sample_name']} → {t['result']}"
        )
