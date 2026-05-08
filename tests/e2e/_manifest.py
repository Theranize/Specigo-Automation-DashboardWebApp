# -*- coding: utf-8 -*-
"""Per-patient phase manifests + patient catalog accessors.

Each manifest is a `list[PhaseStep]` whose items mechanically describe one
patient's phase sequence. The same registry drives both the normal-mode
runners (tests/e2e/{acceptance,rejection}/test_e2e_*.py) and the super-user
runner (tests/e2e/super_user/test_super_user_e2e.py).

Adding a new patient = one builder function + one PATIENT_MANIFESTS entry +
one entry in .claude/test_run_session.json::patients. No new test file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List

from utils.file_utils import load_json
from flows.front_desk_flow import execute_front_desk_registration
from flows.phlebotomist_flow import execute_phlebotomist_flow
from flows.accession_flow import execute_accession_flow
from flows.reassignment_flow import execute_reassignment_flow
from flows.recollection_flow import execute_recollection_flow
from flows.labtech_flow import execute_labtech_search, execute_labtech_tests
from flows.doctor_flow import execute_doctor_flow
from flows.super_user_orchestrator import PhaseStep


_ROOT = Path(__file__).resolve().parents[2]

# Lazy-loaded DDT singletons (one read per process).
_DDT: Dict[str, dict] = {}


def _ddt(rel: str) -> dict:
    if rel not in _DDT:
        _DDT[rel] = load_json(_ROOT / rel)
    return _DDT[rel]


def _entry(data_list: list, key: str, val: str) -> dict:
    return next(e for e in data_list if e[key] == val)


def _with_pid(nested: dict, pid: str) -> dict:
    """Inject patient_id_ref into a nested DDT sub-object (parity with rejection tests)."""
    return {"patient_id_ref": pid, **nested}


# Dummy payment dict used by the FD-only error tests (P7, P11).
_DUMMY_PAYMENT = {"tests": [], "payment": {"home_collection": 0, "cash": 0, "online": 0}}


# Predicate for FD-only error tests: PASS only when the expected error fired
# AND the on-screen message matched the DDT's expected_error block.
def _expected_error_predicate(r: dict) -> bool:
    return bool(r.get("error_found") and r.get("expected_error_matched"))


# --- catalog helpers (read .claude/test_run_session.json) --------------------

_CATALOG_CACHE: Dict[str, dict] = {}


def patient_catalog() -> Dict[str, dict]:
    """Return the patients block from .claude/test_run_session.json (cached)."""
    if "patients" not in _CATALOG_CACHE:
        session = load_json(_ROOT / ".claude/test_run_session.json")
        _CATALOG_CACHE["patients"] = session.get("patients", {}) or {}
        _CATALOG_CACHE["patient_map"] = session.get("_patient_map", {}) or {}
    return _CATALOG_CACHE["patients"]


def mobile_for(pid: str) -> str:
    """Backend mobile for a patient — consumed by the `_mobile_serialise`
    autouse fixture in `conftest.py` to acquire a per-mobile runtime lock,
    so same-mobile tests serialise across xdist workers under
    `--dist worksteal`. Returns "" if the pid has no mapped mobile."""
    if "patient_map" not in _CATALOG_CACHE:
        patient_catalog()  # populates _CATALOG_CACHE["patient_map"]
    return (_CATALOG_CACHE.get("patient_map", {}).get(pid, {}).get("mobile") or "").strip()


def patients_for_file(primary_file: str) -> List[str]:
    """Patient IDs whose primary_file == 'acceptance' or 'rejection'.

    Returns the IDs in catalog declaration order, which is the natural
    P1..P14 sort order today.
    """
    return [
        pid for pid, meta in patient_catalog().items()
        if meta.get("primary_file") == primary_file
    ]


def markers_for(pid: str) -> List[str]:
    """All pytest markers configured for a patient (e.g. ['e2e','acceptance'])."""
    return list(patient_catalog().get(pid, {}).get("markers", []))


# --- per-patient builders ----------------------------------------------------

def _std_acceptance_steps(pid: str) -> List[PhaseStep]:
    """Canonical 5-phase acceptance manifest used by P1, P3, P5, P8, P12, P14."""
    PATIENT   = _ddt("test_data/front_desk/patient_data.json")
    PAYMENT   = _ddt("test_data/front_desk/test_payment_data.json")
    PHLEBO    = _ddt("test_data/phlebotomist/phlebotomist_actions.json")
    ACCESSION = _ddt("test_data/accession/accession_actions.json")
    LT        = _ddt("test_data/lab_technician/labtech_actions.json")
    DOCTOR    = _ddt("test_data/doctor/doctor_actions.json")

    pe   = _entry(PATIENT["patients"], "patient_id_ref", pid)
    tp   = _entry(PAYMENT["patient_test_map"], "patient_id_ref", pid)
    ph_e = _entry(PHLEBO["patients"], "patient_id_ref", pid)
    ac_e = _entry(ACCESSION["patients"], "patient_id_ref", pid)
    lt_e = _entry(LT["patients"], "patient_id_ref", pid)
    dc_e = _entry(DOCTOR["patients"], "patient_id_ref", pid)

    def _lt_runner(page) -> dict:
        ls_r = execute_labtech_search(page, lt_e)
        if ls_r.get("error_found") or not ls_r.get("completed"):
            return ls_r
        return execute_labtech_tests(page, lt_e)

    return [
        PhaseStep("Front Desk",     "fd",     "primary", "front_desk",
                  lambda page: execute_front_desk_registration(page, pe, tp)),
        PhaseStep("Phlebotomist",   "phlebo", "primary", "phlebotomist",
                  lambda page: execute_phlebotomist_flow(page, ph_e)),
        PhaseStep("Accession",      "acc",    "primary", "accession",
                  lambda page: execute_accession_flow(page, ac_e)),
        PhaseStep("Lab Technician", "labt",   "primary", "lab_technician",
                  _lt_runner),
        PhaseStep("Doctor",         "doc",    "primary", "doctor",
                  lambda page: execute_doctor_flow(page, dc_e)),
    ]


def _build_p1(pid: str) -> List[PhaseStep]:
    return _std_acceptance_steps(pid)


def _build_p3(pid: str) -> List[PhaseStep]:
    return _std_acceptance_steps(pid)


def _build_p5(pid: str) -> List[PhaseStep]:
    return _std_acceptance_steps(pid)


def _build_p8(pid: str) -> List[PhaseStep]:
    return _std_acceptance_steps(pid)


def _build_p12(pid: str) -> List[PhaseStep]:
    return _std_acceptance_steps(pid)


def _build_p14(pid: str) -> List[PhaseStep]:
    """P14 — relabel doctor phase to 'Doctor (Partial Approve)'."""
    steps = _std_acceptance_steps(pid)
    steps[-1] = PhaseStep(
        "Doctor (Partial Approve)", "doc", "primary", "doctor",
        steps[-1].runner,
    )
    return steps


def _build_p4(pid: str) -> List[PhaseStep]:
    """P4 — full acceptance + doctor rectify (6 phases)."""
    steps = _std_acceptance_steps(pid)
    DOCTOR_RECTIFY = _ddt("test_data/doctor/doctor_rectify_actions.json")
    rectify_e = _entry(DOCTOR_RECTIFY["patients"], "patient_id_ref", pid)
    steps[-1] = PhaseStep(
        "Doctor (Approve)", "doc", "primary", "doctor", steps[-1].runner,
    )
    steps.append(PhaseStep(
        "Doctor (Rectify)", "doc", "primary", "doctor",
        lambda page: execute_doctor_flow(page, rectify_e),
    ))
    return steps


def _build_p7(pid: str) -> List[PhaseStep]:
    """P7 — single-phase FD limit-error check (PASS iff expected error fires)."""
    PATIENT = _ddt("test_data/front_desk/patient_data.json")
    pe = _entry(PATIENT["patients"], "patient_id_ref", pid)
    return [
        PhaseStep(
            "Front Desk", "fd", "primary", "front_desk",
            lambda page: execute_front_desk_registration(page, pe, _DUMMY_PAYMENT),
            success_predicate=_expected_error_predicate,
        ),
    ]


def _build_p11(pid: str) -> List[PhaseStep]:
    """P11 — single-phase FD duplicate-mobile error check (PASS iff expected error fires)."""
    PATIENT = _ddt("test_data/front_desk/patient_data.json")
    pe = _entry(PATIENT["patients"], "patient_id_ref", pid)
    return [
        PhaseStep(
            "Front Desk", "fd", "primary", "front_desk",
            lambda page: execute_front_desk_registration(page, pe, _DUMMY_PAYMENT),
            success_predicate=_expected_error_predicate,
        ),
    ]


def _build_rejection_3cycle(pid: str, *, a: str, b: str, c: str, d: str, final: str) -> List[PhaseStep]:
    """Canonical 16-phase 3-cycle rejection manifest (P2, P6, P9).

    {a} = first sample rejected at Accession.
    {b} = sample rejected at Lab Technician.
    {c} = sample resampled by Doctor (final approve target).
    {d} = sample reassigned after Doctor resample (e.g. "Serum 2", "WB").
    {final} = "Partial Approve" or "Approve".
    """
    PATIENT   = _ddt("test_data/front_desk/patient_data.json")
    PAYMENT   = _ddt("test_data/front_desk/test_payment_data.json")
    PHLEBO    = _ddt("test_data/phlebotomist/phlebotomist_actions.json")
    ACCESSION = _ddt("test_data/accession/accession_actions.json")
    REASSIGN  = _ddt("test_data/accession/reassignment_actions.json")
    RECOLLECT = _ddt("test_data/phlebotomist/recollection_actions.json")
    LT        = _ddt("test_data/lab_technician/labtech_actions.json")
    DOCTOR    = _ddt("test_data/doctor/doctor_actions.json")

    pe   = _entry(PATIENT["patients"], "patient_id_ref", pid)
    tp   = _entry(PAYMENT["patient_test_map"], "patient_id_ref", pid)
    ph_e = _entry(PHLEBO["patients"], "patient_id_ref", pid)
    ac_e = _entry(ACCESSION["patients"], "patient_id_ref", pid)
    re_e = _entry(REASSIGN["patients"], "patient_id_ref", pid)
    rc_e = _entry(RECOLLECT["patients"], "patient_id_ref", pid)
    lt_e = _entry(LT["patients"], "patient_id_ref", pid)
    dc_e = _entry(DOCTOR["patients"], "patient_id_ref", pid)

    def _acc_reject_then_reassign(page) -> dict:
        r = execute_accession_flow(page, ac_e)
        if r.get("error_found") or not r.get("completed"):
            return r
        return execute_reassignment_flow(page, _with_pid(re_e["cycles"][0], pid))

    def _lt_save_all_runner(page) -> dict:
        rc1 = _with_pid(lt_e["re_cycles"][0], pid)
        ls = execute_labtech_search(page, rc1)
        if ls.get("error_found") or not ls.get("completed"):
            return ls
        return execute_labtech_tests(page, rc1)

    def _lt_save_final_runner(page) -> dict:
        rc2 = _with_pid(lt_e["re_cycles"][1], pid)
        ls = execute_labtech_search(page, rc2)
        if ls.get("error_found") or not ls.get("completed"):
            return ls
        return execute_labtech_tests(page, rc2)

    return [
        PhaseStep("Front Desk",   "fd",     "primary",   "front_desk",
                  lambda page: execute_front_desk_registration(page, pe, tp)),
        PhaseStep("Phlebotomist", "phlebo", "primary",   "phlebotomist",
                  lambda page: execute_phlebotomist_flow(page, ph_e)),
        PhaseStep(f"Accession (Reject {a})",        "acc",    "primary",   "accession",
                  _acc_reject_then_reassign),
        PhaseStep(f"Phlebotomist (Recollect {a})",  "phlebo", "recollect", "phlebotomist",
                  lambda page: execute_recollection_flow(page, _with_pid(rc_e["cycles"][0], pid))),
        PhaseStep(f"Accession (Re-accept {a})",     "acc",    "primary",   "accession",
                  lambda page: execute_accession_flow(page, _with_pid(ac_e["re_accept"][0], pid))),
        PhaseStep(f"Lab Technician (Reject {b})",   "labt",   "primary",   "lab_technician",
                  lambda page: execute_labtech_search(page, lt_e)),
        PhaseStep(f"Accession (Reassign {b})",      "acc",    "reassign",  "accession",
                  lambda page: execute_reassignment_flow(page, _with_pid(re_e["cycles"][1], pid))),
        PhaseStep(f"Phlebotomist (Recollect {b})",  "phlebo", "recollect", "phlebotomist",
                  lambda page: execute_recollection_flow(page, _with_pid(rc_e["cycles"][1], pid))),
        PhaseStep(f"Accession (Re-accept {b})",     "acc",    "primary",   "accession",
                  lambda page: execute_accession_flow(page, _with_pid(ac_e["re_accept"][1], pid))),
        PhaseStep("Lab Technician (Save All)",      "labt",   "primary",   "lab_technician",
                  _lt_save_all_runner),
        PhaseStep(f"Doctor (Resample {c})",         "doc",    "primary",   "doctor",
                  lambda page: execute_doctor_flow(page, dc_e)),
        PhaseStep(f"Accession (Reassign {d})",      "acc",    "reassign",  "accession",
                  lambda page: execute_reassignment_flow(page, _with_pid(re_e["cycles"][2], pid))),
        PhaseStep(f"Phlebotomist (Recollect {d})",  "phlebo", "recollect", "phlebotomist",
                  lambda page: execute_recollection_flow(page, _with_pid(rc_e["cycles"][2], pid))),
        PhaseStep(f"Accession (Re-accept {d})",     "acc",    "primary",   "accession",
                  lambda page: execute_accession_flow(page, _with_pid(ac_e["re_accept"][2], pid))),
        PhaseStep(f"Lab Technician (Save {c})",     "labt",   "primary",   "lab_technician",
                  _lt_save_final_runner),
        PhaseStep(f"Doctor ({final} {c})",          "doc",    "primary",   "doctor",
                  lambda page: execute_doctor_flow(page, _with_pid(dc_e["re_approval"], pid))),
    ]


def _build_p2(pid: str) -> List[PhaseStep]:
    return _build_rejection_3cycle(pid, a="Serum", b="24h", c="LFT", d="Serum 2", final="Partial Approve")


def _build_p6(pid: str) -> List[PhaseStep]:
    return _build_rejection_3cycle(pid, a="Urine", b="Serum", c="CBC", d="WB", final="Approve")


def _build_p9(pid: str) -> List[PhaseStep]:
    return _build_rejection_3cycle(pid, a="Serum", b="24h", c="LFT", d="Serum 2", final="Approve")


def _build_p10(pid: str) -> List[PhaseStep]:
    """P10 — single-cycle accession rejection + LT full + doctor approve + rectify (8 phases)."""
    PATIENT   = _ddt("test_data/front_desk/patient_data.json")
    PAYMENT   = _ddt("test_data/front_desk/test_payment_data.json")
    PHLEBO    = _ddt("test_data/phlebotomist/phlebotomist_actions.json")
    ACCESSION = _ddt("test_data/accession/accession_actions.json")
    REASSIGN  = _ddt("test_data/accession/reassignment_actions.json")
    RECOLLECT = _ddt("test_data/phlebotomist/recollection_actions.json")
    LT        = _ddt("test_data/lab_technician/labtech_actions.json")
    DOCTOR    = _ddt("test_data/doctor/doctor_actions.json")
    DR_RECT   = _ddt("test_data/doctor/doctor_rectify_actions.json")

    pe   = _entry(PATIENT["patients"], "patient_id_ref", pid)
    tp   = _entry(PAYMENT["patient_test_map"], "patient_id_ref", pid)
    ph_e = _entry(PHLEBO["patients"], "patient_id_ref", pid)
    ac_e = _entry(ACCESSION["patients"], "patient_id_ref", pid)
    re_e = _entry(REASSIGN["patients"], "patient_id_ref", pid)
    rc_e = _entry(RECOLLECT["patients"], "patient_id_ref", pid)
    lt_e = _entry(LT["patients"], "patient_id_ref", pid)
    dc_e = _entry(DOCTOR["patients"], "patient_id_ref", pid)
    rect_e = _entry(DR_RECT["patients"], "patient_id_ref", pid)

    def _acc_reject_then_reassign(page) -> dict:
        r = execute_accession_flow(page, ac_e)
        if r.get("error_found") or not r.get("completed"):
            return r
        return execute_reassignment_flow(page, _with_pid(re_e["cycles"][0], pid))

    def _lt_runner(page) -> dict:
        ls = execute_labtech_search(page, lt_e)
        if ls.get("error_found") or not ls.get("completed"):
            return ls
        return execute_labtech_tests(page, lt_e)

    return [
        PhaseStep("Front Desk",   "fd",     "primary",   "front_desk",
                  lambda page: execute_front_desk_registration(page, pe, tp)),
        PhaseStep("Phlebotomist", "phlebo", "primary",   "phlebotomist",
                  lambda page: execute_phlebotomist_flow(page, ph_e)),
        PhaseStep("Accession (Reject 24h)",       "acc",    "primary",   "accession",
                  _acc_reject_then_reassign),
        PhaseStep("Phlebotomist (Recollect 24h)", "phlebo", "recollect", "phlebotomist",
                  lambda page: execute_recollection_flow(page, _with_pid(rc_e["cycles"][0], pid))),
        PhaseStep("Accession (Re-accept 24h)",    "acc",    "primary",   "accession",
                  lambda page: execute_accession_flow(page, _with_pid(ac_e["re_accept"][0], pid))),
        PhaseStep("Lab Technician",               "labt",   "primary",   "lab_technician",
                  _lt_runner),
        PhaseStep("Doctor (Approve)",             "doc",    "primary",   "doctor",
                  lambda page: execute_doctor_flow(page, dc_e)),
        PhaseStep("Doctor (Rectify LFT)",         "doc",    "primary",   "doctor",
                  lambda page: execute_doctor_flow(page, rect_e)),
    ]


def _build_p13(pid: str) -> List[PhaseStep]:
    """P13 — 2-cycle partial rejection (11 phases): Acc rejects Serum, LT rejects 24h, Dr approves all."""
    PATIENT   = _ddt("test_data/front_desk/patient_data.json")
    PAYMENT   = _ddt("test_data/front_desk/test_payment_data.json")
    PHLEBO    = _ddt("test_data/phlebotomist/phlebotomist_actions.json")
    ACCESSION = _ddt("test_data/accession/accession_actions.json")
    REASSIGN  = _ddt("test_data/accession/reassignment_actions.json")
    RECOLLECT = _ddt("test_data/phlebotomist/recollection_actions.json")
    LT        = _ddt("test_data/lab_technician/labtech_actions.json")
    DOCTOR    = _ddt("test_data/doctor/doctor_actions.json")

    pe   = _entry(PATIENT["patients"], "patient_id_ref", pid)
    tp   = _entry(PAYMENT["patient_test_map"], "patient_id_ref", pid)
    ph_e = _entry(PHLEBO["patients"], "patient_id_ref", pid)
    ac_e = _entry(ACCESSION["patients"], "patient_id_ref", pid)
    re_e = _entry(REASSIGN["patients"], "patient_id_ref", pid)
    rc_e = _entry(RECOLLECT["patients"], "patient_id_ref", pid)
    lt_e = _entry(LT["patients"], "patient_id_ref", pid)
    dc_e = _entry(DOCTOR["patients"], "patient_id_ref", pid)

    def _acc_reject_then_reassign(page) -> dict:
        r = execute_accession_flow(page, ac_e)
        if r.get("error_found") or not r.get("completed"):
            return r
        return execute_reassignment_flow(page, _with_pid(re_e["cycles"][0], pid))

    def _lt_save_all_runner(page) -> dict:
        rc1 = _with_pid(lt_e["re_cycles"][0], pid)
        ls = execute_labtech_search(page, rc1)
        if ls.get("error_found") or not ls.get("completed"):
            return ls
        return execute_labtech_tests(page, rc1)

    return [
        PhaseStep("Front Desk",   "fd",     "primary",   "front_desk",
                  lambda page: execute_front_desk_registration(page, pe, tp)),
        PhaseStep("Phlebotomist", "phlebo", "primary",   "phlebotomist",
                  lambda page: execute_phlebotomist_flow(page, ph_e)),
        PhaseStep("Accession (Reject Serum)",        "acc",    "primary",   "accession",
                  _acc_reject_then_reassign),
        PhaseStep("Phlebotomist (Recollect Serum)",  "phlebo", "recollect", "phlebotomist",
                  lambda page: execute_recollection_flow(page, _with_pid(rc_e["cycles"][0], pid))),
        PhaseStep("Accession (Re-accept Serum)",     "acc",    "primary",   "accession",
                  lambda page: execute_accession_flow(page, _with_pid(ac_e["re_accept"][0], pid))),
        PhaseStep("Lab Technician (Reject 24h)",     "labt",   "primary",   "lab_technician",
                  lambda page: execute_labtech_search(page, lt_e)),
        PhaseStep("Accession (Reassign 24h)",        "acc",    "reassign",  "accession",
                  lambda page: execute_reassignment_flow(page, _with_pid(re_e["cycles"][1], pid))),
        PhaseStep("Phlebotomist (Recollect 24h)",    "phlebo", "recollect", "phlebotomist",
                  lambda page: execute_recollection_flow(page, _with_pid(rc_e["cycles"][1], pid))),
        PhaseStep("Accession (Re-accept 24h)",       "acc",    "primary",   "accession",
                  lambda page: execute_accession_flow(page, _with_pid(ac_e["re_accept"][1], pid))),
        PhaseStep("Lab Technician (Save All)",       "labt",   "primary",   "lab_technician",
                  _lt_save_all_runner),
        PhaseStep("Doctor (Approve All)",            "doc",    "primary",   "doctor",
                  lambda page: execute_doctor_flow(page, dc_e)),
    ]


# --- public registry ---------------------------------------------------------

#: Maps patient ID → callable that builds that patient's manifest fresh per run.
PATIENT_MANIFESTS: Dict[str, Callable[[str], List[PhaseStep]]] = {
    "P1":  _build_p1,
    "P2":  _build_p2,
    "P3":  _build_p3,
    "P4":  _build_p4,
    "P5":  _build_p5,
    "P6":  _build_p6,
    "P7":  _build_p7,
    "P8":  _build_p8,
    "P9":  _build_p9,
    "P10": _build_p10,
    "P11": _build_p11,
    "P12": _build_p12,
    "P13": _build_p13,
    "P14": _build_p14,
}

#: Maps patient ID → FLOW_REGISTRY key used by phase_tracker.track in normal-mode runs.
PATIENT_TEST_KEYS: Dict[str, str] = {
    pid: f"test_e2e_{pid.lower()}" for pid in PATIENT_MANIFESTS
}

#: Maps patient ID → FLOW_REGISTRY key used by phase_tracker.track in super-user runs.
SUPER_USER_TEST_KEYS: Dict[str, str] = {
    pid: f"test_super_user_{pid.lower()}" for pid in PATIENT_MANIFESTS
}
