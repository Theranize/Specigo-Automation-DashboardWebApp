"""E2E P10: New patient (Kavita Nair) — accession rejects 24h urine, full LT, doctor approves all + rectifies LFT."""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.phase_tracker import phase_tracker
from flows.front_desk_flow import execute_front_desk_registration
from flows.phlebotomist_flow import execute_phlebotomist_flow
from flows.accession_flow import execute_accession_flow
from flows.reassignment_flow import execute_reassignment_flow
from flows.recollection_flow import execute_recollection_flow
from flows.labtech_flow import execute_labtech_search, execute_labtech_tests
from flows.doctor_flow import execute_doctor_flow
from flows.logout_flow import execute_logout

_ROOT = Path(__file__).resolve().parents[3]
_TEST = "test_e2e_p10_new_patient_partial"

SESSION              = load_json(_ROOT / ".claude/test_run_session.json")
PATIENT_DATA         = load_json(_ROOT / "test_data/front_desk/patient_data.json")
PAYMENT_DATA         = load_json(_ROOT / "test_data/front_desk/test_payment_data.json")
PHLEBO_DATA          = load_json(_ROOT / "test_data/phlebotomist/phlebotomist_actions.json")
ACCESSION_DATA       = load_json(_ROOT / "test_data/accession/accession_actions.json")
REASSIGN_DATA        = load_json(_ROOT / "test_data/accession/reassignment_actions.json")
RECOLLECT_DATA       = load_json(_ROOT / "test_data/phlebotomist/recollection_actions.json")
LT_DATA              = load_json(_ROOT / "test_data/lab_technician/labtech_actions.json")
DOCTOR_DATA          = load_json(_ROOT / "test_data/doctor/doctor_actions.json")
DOCTOR_RECTIFY_DATA  = load_json(_ROOT / "test_data/doctor/doctor_rectify_actions.json")


def _entry(data_list: list, key: str, pid: str) -> dict:
    return next(e for e in data_list if e[key] == pid)


def _with_pid(nested: dict, pid: str) -> dict:
    """Inject patient_id_ref into a nested DDT sub-object for flows that require it."""
    return {"patient_id_ref": pid, **nested}


def _shot(page, label: str) -> str:
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/p10_{label}.png"
    page.screenshot(path=path)
    return path


def _logout(page) -> None:
    execute_logout(page)
    page.wait_for_load_state("networkidle")
    page.goto(page.context.base_url + "login")
    page.wait_for_load_state("networkidle")


@pytest.mark.e2e
@pytest.mark.rejection
@pytest.mark.rectification
def test_e2e_p10_new_patient_partial(page, login_as):
    """P10: New user Kavita Nair — Acc(reject 24h urine) → LT(full) → Doctor(approve all) → Doctor(rectify LFT)."""
    pid = SESSION["e2e_assignments"][_TEST]["patient_id"]

    ac_e  = _entry(ACCESSION_DATA["patients"],  "patient_id_ref", pid)
    re_e  = _entry(REASSIGN_DATA["patients"],   "patient_id_ref", pid)
    rc_e  = _entry(RECOLLECT_DATA["patients"],  "patient_id_ref", pid)
    lt_e  = _entry(LT_DATA["patients"],         "patient_id_ref", pid)
    doc_e = _entry(DOCTOR_DATA["patients"],     "patient_id_ref", pid)

    # ── Phase 1: Front Desk (new user registration) ──────────────────────────
    print(f"\n[{pid}] --- Phase 1: Front Desk new user registration ---")
    login_as("front_desk")
    with phase_tracker.track(page, pid, "Front Desk", _TEST):
        fd_r = execute_front_desk_registration(
            page,
            _entry(PATIENT_DATA["patients"], "patient_id_ref", pid),
            _entry(PAYMENT_DATA["patient_test_map"], "patient_id_ref", pid),
        )
        _shot(page, "01_fd")
        if fd_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 1 FD: {fd_r['error_message']}")
        assert fd_r["completed"]
        print(f"[{pid}] Phase 1 DONE: Front Desk registration complete")
    _logout(page)

    # ── Phase 2: Phlebotomist — initial collection ───────────────────────────
    print(f"\n[{pid}] --- Phase 2: Phlebotomist initial collection ---")
    login_as("phlebotomist")
    with phase_tracker.track(page, pid, "Phlebotomist", _TEST):
        ph_r = execute_phlebotomist_flow(
            page, _entry(PHLEBO_DATA["patients"], "patient_id_ref", pid)
        )
        _shot(page, "02_phlebo")
        if ph_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 2 Phlebo: {ph_r['error_message']}")
        assert ph_r["completed"]
        print(f"[{pid}] Phase 2 DONE: Phlebotomist initial collection complete")
    _logout(page)

    # ── Phase 3+4: Accession — reject 24h urine + reassign ──────────────────
    print(f"\n[{pid}] --- Phase 3+4: Accession reject 24h urine + reassign ---")
    login_as("accession")
    with phase_tracker.track(page, pid, "Accession (Reject 24h)", _TEST):
        ac_r = execute_accession_flow(page, ac_e)
        _shot(page, "03_acc_reject")
        if ac_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 3 Accession reject: {ac_r['error_message']}")
        assert ac_r["completed"]

        re1_r = execute_reassignment_flow(page, re_e["cycles"][0])
        _shot(page, "04_reassign_24h")
        if re1_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 4 Reassign 24h urine: {re1_r['error_message']}")
        assert re1_r["completed"]
        print(f"[{pid}] Phase 3+4 DONE: Accession rejected + reassigned 24h urine")
    _logout(page)

    # ── Phase 5: Phlebotomist — recollect 24h urine ──────────────────────────
    print(f"\n[{pid}] --- Phase 5: Phlebo recollect 24h urine ---")
    login_as("phlebotomist")
    with phase_tracker.track(page, pid, "Phlebotomist (Recollect 24h)", _TEST):
        rc1_r = execute_recollection_flow(page, rc_e["cycles"][0])
        _shot(page, "05_recollect_24h")
        if rc1_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 5 Recollect 24h urine: {rc1_r['error_message']}")
        assert rc1_r["completed"]
        print(f"[{pid}] Phase 5 DONE: 24h urine recollected")
    _logout(page)

    # ── Phase 6: Accession — re-accept 24h urine ─────────────────────────────
    print(f"\n[{pid}] --- Phase 6: Accession re-accept 24h urine ---")
    login_as("accession")
    with phase_tracker.track(page, pid, "Accession (Re-accept 24h)", _TEST):
        ac2_r = execute_accession_flow(page, _with_pid(ac_e["re_accept"][0], pid))
        _shot(page, "06_acc_accept_24h")
        if ac2_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 6 Accession re-accept 24h urine: {ac2_r['error_message']}")
        assert ac2_r["completed"]
        print(f"[{pid}] Phase 6 DONE: Recollected 24h urine accepted at accession")
    _logout(page)

    # ── Phase 7: Lab Technician — accept all + save all 7 tests ──────────────
    print(f"\n[{pid}] --- Phase 7: LT accept all samples + save all 7 tests ---")
    login_as("lab_technician")
    with phase_tracker.track(page, pid, "Lab Technician", _TEST):
        ls_r = execute_labtech_search(page, lt_e)
        _shot(page, "07_lt_search")
        if ls_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 7 LT search: {ls_r['error_message']}")
        assert ls_r["completed"]

        lt_r = execute_labtech_tests(page, lt_e)
        _shot(page, "07_lt_tests")
        if lt_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 7 LT tests: {lt_r['error_message']}")
        assert lt_r["completed"]
        for t in lt_r["test_results"]:
            assert t["error"] is None, f"[{pid}] LT error: {t['test_name']} — {t['error']}"
        print(f"[{pid}] Phase 7 DONE: LT saved all 7 tests")
    _logout(page)

    # ── Phase 8: Doctor — approve all tests ──────────────────────────────────
    print(f"\n[{pid}] --- Phase 8: Doctor approve all tests ---")
    login_as("doctor")
    with phase_tracker.track(page, pid, "Doctor (Approve)", _TEST):
        dr_r = execute_doctor_flow(page, doc_e)
        _shot(page, "08_doctor_approve")
        if dr_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 8 Doctor approve: {dr_r['error_message']}")
        assert dr_r["completed"]
        for t in dr_r["test_results"]:
            assert t["error"] is None, f"Doctor approve error: {t['test_name']} - {t['error']}"
        print(f"[{pid}] Phase 8 DONE: Doctor approved all tests")
    _logout(page)

    # ── Phase 9: Doctor — rectify LFT ────────────────────────────────────────
    print(f"\n[{pid}] --- Phase 9: Doctor rectify LFT ---")
    login_as("doctor")
    with phase_tracker.track(page, pid, "Doctor (Rectify LFT)", _TEST):
        rc_r = execute_doctor_flow(page, _entry(DOCTOR_RECTIFY_DATA["patients"], "patient_id_ref", pid))
        _shot(page, "09_doctor_rectify")
        if rc_r["error_found"]:
            pytest.fail(f"[{pid}] Phase 9 Doctor rectify LFT: {rc_r['error_message']}")
        assert rc_r["completed"]
        for t in rc_r["test_results"]:
            assert t["error"] is None, f"Doctor rectify error: {t['test_name']} - {t['error']}"
        print(f"[{pid}] Phase 9 DONE: Doctor rectified LFT")
    _logout(page)
