"""E2E P14: New patient (Sanjay Mehta) — 3 tests, partial LT params, doctor partial_approve."""

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
_TEST = "test_e2e_p14_partial_approve"

SESSION        = load_json(_ROOT / ".claude/test_run_session.json")
PATIENT_DATA   = load_json(_ROOT / "test_data/front_desk/patient_data.json")
PAYMENT_DATA   = load_json(_ROOT / "test_data/front_desk/test_payment_data.json")
PHLEBO_DATA    = load_json(_ROOT / "test_data/phlebotomist/phlebotomist_actions.json")
ACCESSION_DATA = load_json(_ROOT / "test_data/accession/accession_actions.json")
LT_DATA        = load_json(_ROOT / "test_data/lab_technician/labtech_actions.json")
DOCTOR_DATA    = load_json(_ROOT / "test_data/doctor/doctor_actions.json")


def _entry(data_list: list, key: str, pid: str) -> dict:
    return next(e for e in data_list if e[key] == pid)


def _shot(page, label: str) -> str:
    os.makedirs("artifacts", exist_ok=True)
    path = f"artifacts/p14_{label}.png"
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
def test_e2e_p14_partial_approve(page, login_as):
    """P14: New patient Sanjay Mehta — CBC+RFT+LFT, partial LT params, doctor partial_approve all 3."""
    pid = SESSION["e2e_assignments"][_TEST]["patient_id"]

    # ── Phase 1: Front Desk ──────────────────────────────────
    login_as("front_desk")
    with phase_tracker.track(page, pid, "Front Desk", _TEST):
        pe   = _entry(PATIENT_DATA["patients"], "patient_id_ref", pid)
        tp   = _entry(PAYMENT_DATA["patient_test_map"], "patient_id_ref", pid)
        fd_r = execute_front_desk_registration(page, pe, tp)
        _shot(page, "fd")
        if fd_r["error_found"]:
            pytest.fail(f"[{pid}] FD: {fd_r['error_message']}")
        assert fd_r["completed"]
        samples = runtime_state.get_samples()
        assert len(samples) > 0
        _tbl(pid, "FRONT DESK — SAMPLES", ["Sample", "Sub Dept", "ID"],
             [(s["name"], s["sub_department"], s["id"]) for s in samples])
    _logout(page)

    # ── Phase 2: Phlebotomist (WB + Serum ON) ───────────────
    login_as("phlebotomist")
    with phase_tracker.track(page, pid, "Phlebotomist", _TEST):
        ph_r = execute_phlebotomist_flow(page, _entry(PHLEBO_DATA["patients"], "patient_id_ref", pid))
        _shot(page, "phlebo")
        if ph_r["error_found"]:
            pytest.fail(f"[{pid}] Phlebo: {ph_r['error_message']}")
        assert ph_r["completed"]
        _tbl(pid, "PHLEBOTOMIST — TOGGLES", ["Sample", "Sub Dept", "ID", "Action", "Result"],
             [(t["sample"], t["sub_department"], t.get("sample_id", ""), t["action"], t.get("result", ""))
              for t in ph_r["toggle_results"]])
    _logout(page)

    # ── Phase 3: Accession (accept WB + Serum) ───────────────
    login_as("accession")
    with phase_tracker.track(page, pid, "Accession", _TEST):
        ac_r = execute_accession_flow(page, _entry(ACCESSION_DATA["patients"], "patient_id_ref", pid))
        _shot(page, "acc")
        if ac_r["error_found"]:
            pytest.fail(f"[{pid}] Accession: {ac_r['error_message']}")
        assert ac_r["completed"]
        _tbl(pid, "ACCESSION — ACTIONS", ["Sample", "Sub Dept", "ID", "Action", "Result"],
             [(a["sample"], a["sub_department"], a.get("sample_id", ""), a["action"], a.get("result", ""))
              for a in ac_r["action_results"]])
    _logout(page)

    # ── Phase 4: Lab Technician (partial params for CBC/RFT/LFT)
    login_as("lab_technician")
    with phase_tracker.track(page, pid, "Lab Technician", _TEST):
        lt_e = _entry(LT_DATA["patients"], "patient_id_ref", pid)
        ls_r = execute_labtech_search(page, lt_e)
        _shot(page, "lt_search")
        if ls_r["error_found"]:
            pytest.fail(f"[{pid}] LT Search: {ls_r['error_message']}")
        assert ls_r["completed"]
        if ls_r.get("action_results"):
            _tbl(pid, "LAB TECH — SAMPLE ACCEPTANCE", ["Sample", "Sub Dept", "ID", "Action", "Result"],
                 [(a["sample"], a["sub_department"], a.get("sample_id", ""), a["action"], a.get("result", ""))
                  for a in ls_r["action_results"]])
        lt_r = execute_labtech_tests(page, lt_e)
        _shot(page, "lt_tests")
        if lt_r["error_found"]:
            pytest.fail(f"[{pid}] LT Tests: {lt_r['error_message']}")
        assert lt_r["completed"]
        _tbl(pid, "LAB TECH — TEST RESULTS", ["Test Name", "Action", "Result"],
             [(t["test_name"], t["action"], t.get("result", "")) for t in lt_r["test_results"]])
        for t in lt_r["test_results"]:
            assert t["error"] is None, f"[{pid}] LT error: {t['test_name']} — {t['error']}"
    _logout(page)

    # ── Phase 5: Doctor (partial_approve CBC + RFT + LFT) ───
    login_as("doctor")
    with phase_tracker.track(page, pid, "Doctor (Partial Approve)", _TEST):
        dr_r = execute_doctor_flow(page, _entry(DOCTOR_DATA["patients"], "patient_id_ref", pid))
        _shot(page, "doctor")
        if dr_r["error_found"]:
            pytest.fail(f"[{pid}] Doctor: {dr_r['error_message']}")
        assert dr_r["completed"]
        _tbl(pid, "DOCTOR — PARTIAL APPROVE", ["Test Name", "Action", "Result"],
             [(t["test_name"], t["action"], t.get("result", f"ERR:{t.get('error')}"))
              for t in dr_r["test_results"]])
        for t in dr_r["test_results"]:
            assert t["error"] is None, f"[{pid}] Doctor error: {t['test_name']} — {t['error']}"
    _logout(page)
