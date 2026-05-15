"""E2E P4: Full acceptance with doctor rectification — approve 5 tests then rectify RFT and LFT."""

import os
from pathlib import Path

import pytest
from utils.file_utils import load_json
from utils.phase_tracker import phase_tracker
from flows.front_desk_flow import execute_front_desk_registration
from flows.phlebotomist_flow import execute_phlebotomist_flow
from flows.accession_flow import execute_accession_flow
from flows.labtech_flow import execute_labtech_search, execute_labtech_tests
from flows.doctor_flow import execute_doctor_flow
from flows.logout_flow import execute_logout
from state import runtime_state

_ROOT = Path(__file__).resolve().parents[3]
_TEST = "test_e2e_p4_rectification"

SESSION        = load_json(_ROOT / ".claude/test_run_session.json")
PATIENT_DATA   = load_json(_ROOT / "test_data/front_desk/patient_data.json")
PAYMENT_DATA   = load_json(_ROOT / "test_data/front_desk/test_payment_data.json")
PHLEBO_DATA    = load_json(_ROOT / "test_data/phlebotomist/phlebotomist_actions.json")
ACCESSION_DATA = load_json(_ROOT / "test_data/accession/accession_actions.json")
LT_DATA        = load_json(_ROOT / "test_data/lab_technician/labtech_actions.json")
DOCTOR_DATA         = load_json(_ROOT / "test_data/doctor/doctor_actions.json")
DOCTOR_RECTIFY_DATA = load_json(_ROOT / "test_data/doctor/doctor_rectify_actions.json")


def _entry(data_list: list, key: str, pid: str) -> dict:
    return next(e for e in data_list if e[key] == pid)


def _shot(page, label: str) -> str:
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/p4_{label}.png"
    page.screenshot(path=path)
    return path


def _logout(page) -> None:
    execute_logout(page)
    page.wait_for_load_state("networkidle")
    page.goto(page.context.base_url + "login")
    page.wait_for_load_state("networkidle")


def _tbl(pid: str, header: str, cols: list, rows: list) -> None:
    """Print a fixed-width table to stdout for phase result visibility."""
    w = [max(len(c), 20) for c in cols]
    sep = " | ".join("-" * x for x in w)
    fmt = " | ".join(f"{{:<{x}}}" for x in w)
    print(f"\n{'=' * 75}\n[{pid}] {header}")
    print(fmt.format(*cols))
    print(sep)
    for r in rows:
        print(fmt.format(*[str(v)[:x] for v, x in zip(r, w)]))
    print("=" * 75)


@pytest.mark.e2e
@pytest.mark.acceptance
@pytest.mark.rectification
def test_e2e_p4_rectification(page, login_as):
    """P4: FD → Phlebo → Accession → LT → Doctor(approve 5) → Doctor(rectify RFT+LFT)."""
    pid = SESSION["e2e_assignments"][_TEST]["patient_id"]

    # ── Phase 1: Front Desk ──────────────────────────────────
    login_as("front_desk")
    with phase_tracker.track(page, pid, "Front Desk", _TEST):
        pe   = _entry(PATIENT_DATA["patients"], "patient_id_ref", pid)
        tp   = _entry(PAYMENT_DATA["patient_test_map"], "patient_id_ref", pid)
        fd_r = execute_front_desk_registration(page, pe, tp)
        if fd_r["error_found"]:
            pytest.fail(f"[{pid}] FD: {fd_r['error_message']}\n  {_shot(page, 'fd')}")
        assert fd_r["completed"]
        samples = runtime_state.get_samples()
        assert len(samples) > 0
        _tbl(pid, "FRONT DESK — SAMPLES", ["Sample", "Sub Dept", "ID"],
             [(s["name"], s["sub_department"], s["id"]) for s in samples])
    _logout(page)

    # ── Phase 2: Phlebotomist ────────────────────────────────
    login_as("phlebotomist")
    with phase_tracker.track(page, pid, "Phlebotomist", _TEST):
        ph_r = execute_phlebotomist_flow(page, _entry(PHLEBO_DATA["patients"], "patient_id_ref", pid))
        if ph_r["error_found"]:
            pytest.fail(f"[{pid}] Phlebo: {ph_r['error_message']}\n  {_shot(page, 'phlebo')}")
        assert ph_r["completed"]
        _tbl(pid, "PHLEBOTOMIST — TOGGLES", ["Sample", "Sub Dept", "ID", "Action", "Result"],
             [(t["sample"], t["sub_department"], t.get("sample_id", ""), t["action"], t.get("result", ""))
              for t in ph_r["toggle_results"]])
    _logout(page)

    # ── Phase 3: Accession ───────────────────────────────────
    login_as("accession")
    with phase_tracker.track(page, pid, "Accession", _TEST):
        ac_r = execute_accession_flow(page, _entry(ACCESSION_DATA["patients"], "patient_id_ref", pid))
        if ac_r["error_found"]:
            pytest.fail(f"[{pid}] Accession: {ac_r['error_message']}\n  {_shot(page, 'acc')}")
        assert ac_r["completed"]
        _tbl(pid, "ACCESSION — ACTIONS", ["Sample", "Sub Dept", "ID", "Action", "Result"],
             [(a["sample"], a["sub_department"], a.get("sample_id", ""), a["action"], a.get("result", ""))
              for a in ac_r["action_results"]])
    _logout(page)

    # ── Phase 4: Lab Technician ──────────────────────────────
    login_as("lab_technician")
    with phase_tracker.track(page, pid, "Lab Technician", _TEST):
        lt_e = _entry(LT_DATA["patients"], "patient_id_ref", pid)
        ls_r = execute_labtech_search(page, lt_e)
        if ls_r["error_found"]:
            pytest.fail(f"[{pid}] LT Search: {ls_r['error_message']}\n  {_shot(page, 'lt_search')}")
        assert ls_r["completed"]
        lt_r = execute_labtech_tests(page, lt_e)
        if lt_r["error_found"]:
            pytest.fail(f"[{pid}] LT Tests: {lt_r['error_message']}\n  {_shot(page, 'lt_tests')}")
        assert lt_r["completed"]
        _tbl(pid, "LAB TECH — TEST RESULTS", ["Test Name", "Action", "Result"],
             [(t["test_name"], t["action"], t.get("result", "")) for t in lt_r["test_results"]])
        for t in lt_r["test_results"]:
            assert t["error"] is None, f"[{pid}] LT error: {t['test_name']} — {t['error']}"
    _logout(page)

    # ── Phase 5: Doctor — approve 5 tests ───────────────────
    login_as("doctor")
    with phase_tracker.track(page, pid, "Doctor (Approve)", _TEST):
        dr_r = execute_doctor_flow(page, _entry(DOCTOR_DATA["patients"], "patient_id_ref", pid))
        if dr_r["error_found"]:
            pytest.fail(f"[{pid}] Doctor approve: {dr_r['error_message']}\n  {_shot(page, 'dr_approve')}")
        assert dr_r["completed"]
        _tbl(pid, "DOCTOR — APPROVE", ["Test Name", "Action", "Result"],
             [(t["test_name"], t["action"], t.get("result", f"ERR:{t.get('error')}"))
              for t in dr_r["test_results"]])
    _logout(page)

    # ── Phase 6: Doctor — rectify RFT + LFT ─────────────────
    login_as("doctor")
    with phase_tracker.track(page, pid, "Doctor (Rectify)", _TEST):
        rc_r = execute_doctor_flow(page, _entry(DOCTOR_RECTIFY_DATA["patients"], "patient_id_ref", pid))
        if rc_r["error_found"]:
            pytest.fail(f"[{pid}] Doctor rectify: {rc_r['error_message']}\n  {_shot(page, 'dr_rectify')}")
        assert rc_r["completed"]
        _tbl(pid, "DOCTOR — RECTIFY", ["Test Name", "Action", "Result"],
             [(t["test_name"], t["action"], t.get("result", f"ERR:{t.get('error')}"))
              for t in rc_r["test_results"]])
    _logout(page)

