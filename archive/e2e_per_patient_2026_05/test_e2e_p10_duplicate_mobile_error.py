"""E2E P11: New patient form with existing mobile → verify error and pass."""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.phase_tracker import phase_tracker
from flows.front_desk_flow import execute_front_desk_registration
from flows.logout_flow import execute_logout

_ROOT = Path(__file__).resolve().parents[3]
_TEST = "test_e2e_p11_duplicate_mobile_error"

SESSION      = load_json(_ROOT / ".claude/test_run_session.json")
PATIENT_DATA = load_json(_ROOT / "test_data/front_desk/patient_data.json")

_DUMMY_PAYMENT = {"tests": [], "payment": {"home_collection": 0, "cash": 0, "online": 0}}


def _entry(data_list: list, key: str, val: str) -> dict:
    return next(e for e in data_list if e[key] == val)


def _shot(page, label: str) -> str:
    os.makedirs("artifacts/success", exist_ok=True)
    path = f"artifacts/success/{label}.png"
    page.screenshot(path=path)
    return path


@pytest.mark.e2e
@pytest.mark.acceptance
def test_e2e_p11_duplicate_mobile_error(page, login_as):
    """P11: Registering a new patient with an already-registered mobile must show the duplicate-mobile error.

    Expected: FD shows 'Patient record(s) found with the given mobile number'.
    Test passes when the expected error appears and the message matches the DDT.
    """
    pid = SESSION["e2e_assignments"][_TEST]["patient_id"]
    pe  = _entry(PATIENT_DATA["patients"], "patient_id_ref", pid)

    expected_err = pe.get("expected_error", {})
    assert expected_err.get("should_appear"), (
        f"[{pid}] DDT misconfiguration: expected_error.should_appear must be true for P11"
    )

    login_as("front_desk")
    with phase_tracker.track(page, pid, "Front Desk", _TEST):
        fd_r = execute_front_desk_registration(page, pe, _DUMMY_PAYMENT)

        if not fd_r["error_found"]:
            shot = _shot(page, f"{pid}-fd-no-error")
            pytest.fail(
                f"[{pid}] Expected duplicate-mobile error did NOT appear. "
                f"Screenshot: {shot}"
            )

        if not fd_r["expected_error_matched"]:
            shot = _shot(page, f"{pid}-fd-wrong-error")
            pytest.fail(
                f"[{pid}] Error appeared but message did not match.\n"
                f"  Expected : {expected_err['message']}\n"
                f"  Got      : {fd_r['error_message']}\n"
                f"  Screenshot: {shot}"
            )

        # Expected error appeared with correct message — take success screenshot and pass
        shot = _shot(page, f"p11-e2e-fd-duplicate-mobile-error")
        print(
            f"\n[{pid}] PASS — Duplicate-mobile error correctly raised.\n"
            f"  Message   : {fd_r['error_message']}\n"
            f"  Screenshot: {shot}"
        )

    execute_logout(page)
