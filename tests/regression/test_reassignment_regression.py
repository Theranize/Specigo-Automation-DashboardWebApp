"""Re-Assignment Log — Regression test (standalone).

Prerequisite: runtime_state must be populated by a prior FD registration
(patient_name, mobile_number, and samples with IDs).
"""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.test_helpers import smart_parametrize
from flows.reassignment_flow import execute_reassignment_flow
from state import runtime_state

_ROOT = Path(__file__).resolve().parents[2]
REASSIGNMENT_DATA = load_json(
    _ROOT / "test_data/accession/reassignment_actions.json"
)
PATIENT_IDS = [p["patient_id_ref"] for p in REASSIGNMENT_DATA["patients"]]


def _shot(page, pid, label):
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/reassignment_{pid}_{label}.png"
    page.screenshot(path=path)
    return path


@pytest.mark.regression
@smart_parametrize("patient_id", PATIENT_IDS)
def test_accession_reassignment(page, login_as, patient_id=None):
    """Assign rejected samples back to phlebotomist via Re-Assignment Log."""
    assert runtime_state.get_value("patient_name"), (
        f"[{patient_id}] patient_name not in runtime_state — "
        "run front desk registration first"
    )
    assert runtime_state.get_value("mobile_number"), (
        f"[{patient_id}] mobile_number not in runtime_state — "
        "run front desk registration first"
    )
    assert len(runtime_state.get_samples()) > 0, (
        f"[{patient_id}] no samples in runtime_state — "
        "run front desk registration first"
    )

    patient_id = patient_id or PATIENT_IDS[0]
    login_as("accession")

    entry = next(
        p for p in REASSIGNMENT_DATA["patients"]
        if p["patient_id_ref"] == patient_id
    )
    result = execute_reassignment_flow(page, entry["cycles"][0])

    if result["error_found"]:
        pytest.fail(
            f"[{patient_id}] {result['error_message']}\n"
            f"  {_shot(page, patient_id, 'error')}"
        )

    assert result["completed"], f"[{patient_id}] Reassignment flow did not complete"

    for a in result["action_results"]:
        assert a.get("result") == "assigned", (
            f"[{patient_id}] Sample not assigned: "
            f"{a['sample_name']} | {a.get('sample_id')}"
        )

    print(f"\n[{patient_id}] REASSIGNMENT — RESULTS")
    for a in result["action_results"]:
        print(
            f"  {a['sample_name']} | {a['sub_department']} | "
            f"{a.get('sample_id', '')} → {a['result']}"
        )
