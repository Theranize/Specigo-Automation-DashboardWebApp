"""Accession Sample Verification — Regression test (standalone)."""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.test_helpers import smart_parametrize
from flows.accession_flow import execute_accession_flow
from state import runtime_state

_ROOT = Path(__file__).resolve().parents[2]
ACCESSION_DATA = load_json(_ROOT / "test_data/accession/accession_actions.json")
PATIENT_IDS = [p["patient_id_ref"] for p in ACCESSION_DATA["patients"]]


def _shot(page, pid, label):
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/accession_{pid}_{label}.png"
    page.screenshot(path=path)
    return path


@pytest.mark.regression
@smart_parametrize("patient_id", PATIENT_IDS)
def test_accession_sample_verification(page, login_as, patient_id):
    """Verify and accept/reject samples for each patient scenario."""
    assert runtime_state.get_value("patient_name"), (
        f"[{patient_id}] patient_name not in runtime_state — run front desk first"
    )
    login_as("accession")
    entry = next(p for p in ACCESSION_DATA["patients"] if p["patient_id_ref"] == patient_id)
    result = execute_accession_flow(page, entry)
    if result["error_found"]:
        pytest.fail(f"[{patient_id}] {result['error_message']}\n  {_shot(page, patient_id, 'error')}")
    assert result["completed"], f"[{patient_id}] Accession flow did not complete"
    for a in result["action_results"]:
        assert a.get("result") is not None, f"Action result not set: {a['sample']}"
