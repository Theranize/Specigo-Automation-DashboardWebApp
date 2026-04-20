import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.test_helpers import smart_parametrize
from flows.front_desk_flow import execute_front_desk_registration
from state import runtime_state

# ── Resolve paths relative to project root ──────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ── Load test data at module level for parametrize IDs ──────
PATIENT_DATA = load_json(_PROJECT_ROOT / "test_data/front_desk/patient_data.json")
TEST_PAYMENT_DATA = load_json(_PROJECT_ROOT / "test_data/front_desk/test_payment_data.json")
PATIENT_IDS = [p["patient_id_ref"] for p in PATIENT_DATA["patients"]]


def _get_patient_entry(patient_id: str) -> dict:
    """Look up patient entry by patient_id_ref."""
    return next(
        p for p in PATIENT_DATA["patients"]
        if p["patient_id_ref"] == patient_id
    )


def _get_test_payment_entry(patient_id: str) -> dict:
    """Look up test/payment entry by patient_id_ref."""
    return next(
        t for t in TEST_PAYMENT_DATA["patient_test_map"]
        if t["patient_id_ref"] == patient_id
    )


def _take_screenshot(page, patient_id: str, label: str) -> str:
    """Capture a screenshot and return the file path."""
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/{patient_id}_{label}.png"
    page.screenshot(path=path)
    return path


def _print_runtime_samples(patient_id: str, display_name: str) -> None:
    """Print patient-wise sample data from runtime_state for verification."""
    samples = runtime_state.get_samples()
    print(f"\n{'=' * 70}")
    print(f"[{patient_id}] {display_name} — RUNTIME STATE SAMPLES")
    print(f"{'Sample':<25} | {'Sub Dept':<15} | {'ID'}")
    print(f"{'-' * 70}")
    for s in samples:
        print(f"{s['name']:<25} | {s['sub_department']:<15} | {s['id']}")
    print(f"{'=' * 70}")


@pytest.mark.regression
@smart_parametrize("patient_id", PATIENT_IDS)
def test_front_desk_scenario(page, login_as, patient_id):
    """Execute front desk registration for a single patient scenario.

    DDT-driven error logic:
      - Error found + DDT expected + message matches  → PASS
      - Error found + DDT not expected                → FAIL
      - Error found + DDT expected + message mismatch → FAIL
      - No error    + DDT expected error              → FAIL
      - No error    + DDT not expected                → success path
    """
    login_as("front_desk")

    patient_entry = _get_patient_entry(patient_id)
    test_payment_entry = _get_test_payment_entry(patient_id)
    expected_error = patient_entry["expected_error"]
    intent = patient_entry["patient_intent"]

    result = execute_front_desk_registration(
        page, patient_entry, test_payment_entry
    )

    display_name = result.get("patient_display_name", patient_id)

    # ── Error path (DDT-driven) ───────────────────────────
    if result["error_found"]:
        screenshot = _take_screenshot(page, patient_id, "error")
        assert expected_error["should_appear"], (
            f"[{patient_id}] Unexpected error: {result['error_message']}\n"
            f"  Screenshot: {screenshot}"
        )
        assert result["error_message"] == expected_error["message"], (
            f"[{patient_id}] Error mismatch:\n"
            f"  expected: '{expected_error['message']}'\n"
            f"  got:      '{result['error_message']}'"
        )
        print(f"\n[{patient_id}] {display_name} — Expected error validated")
        print(f"  Error: {result['error_message']}")
        print(f"  Screenshot: {screenshot}")
        return

    # ── Expected error didn't appear ──────────────────────
    assert not expected_error["should_appear"], (
        f"[{patient_id}] Expected error '{expected_error['message']}' "
        f"but none appeared"
    )

    # ── Success path ──────────────────────────────────────
    assert result["completed"], f"[{patient_id}] Flow did not complete"

    # ── Print runtime_state samples (before assertions) ───
    _print_runtime_samples(patient_id, display_name)

    # ── Assertions ────────────────────────────────────────
    samples = runtime_state.get_samples()

    assert runtime_state.get_value("balance") is not None, (
        f"[{patient_id}] Balance not captured"
    )
    assert len(samples) > 0, (
        f"[{patient_id}] No samples captured in runtime_state"
    )
    for sample in samples:
        assert "sub_department" in sample, (
            f"[{patient_id}] Sample missing sub_department: {sample}"
        )
        assert sample["id"], (
            f"[{patient_id}] Sample ID is empty: {sample}"
        )
    assert runtime_state.get_value("patient_name"), (
        f"[{patient_id}] Patient name not stored"
    )
    assert runtime_state.get_value("patient_mobile"), (
        f"[{patient_id}] Patient mobile not stored"
    )

    # ── Existing user: mobile auto-fill equality check ────
    if intent["search_before_add"]:
        mobile_auto = runtime_state.get_value("mobile_auto_filled")
        assert mobile_auto is not None, (
            f"[{patient_id}] Mobile auto-fill not verified after search"
        )
        expected_mobile = runtime_state.get_value("mobile_number")
        assert mobile_auto == expected_mobile, (
            f"[{patient_id}] Mobile auto-fill mismatch: "
            f"expected '{expected_mobile}', got '{mobile_auto}'"
        )
