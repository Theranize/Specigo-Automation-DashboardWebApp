# -*- coding: utf-8 -*-
"""
Phase-level tracking for patient e2e workflows.

Tracks per-patient, per-phase execution status for structured reporting.

Statuses:
    PASSED        — phase completed without exception
    FAILED        — phase raised an exception / pytest.fail()
    NOT EXECUTED  — phase not attempted (prior phase caused test to abort)

Artifact directory layout:
    artifacts/
    ├── success/     — one screenshot per PASSED phase, named by convention
    └── failures/    — one screenshot per FAILED phase, named by convention

Naming convention:
    Success : {pid}-{flow}-{phase}.png
    Failure : {pid}-{flow}-{phase}-{issuetype}{seq}.png

    pid       = patient_id lowercased, non-alphanumeric stripped  (e.g. p1, p2)
    flow      = short flow key from _FLOW_SHORT map              (e.g. e2eacceptance)
    phase     = phase name lowercased, non-alphanumeric stripped  (e.g. accession)
    issuetype = keyword derived from phase name                   (e.g. acceptissue)
    seq       = per-(pid, flow, phase) failure counter, starts at 1

    Examples:
        artifacts/success/p1-e2eacceptance-frontdesk.png
        artifacts/success/p2-e2eb1accession-phlebotomist.png
        artifacts/failures/p2-e2eb1accession-accession-acceptissue1.png
        artifacts/failures/p3-e2eb2labtech-labtechnician-labissue1.png

Usage in test functions:
    from utils.phase_tracker import phase_tracker

    _TEST = "test_e2e_acceptance"   # must match the key in _FLOW_SHORT

    with phase_tracker.track(page, pid, "Accession", _TEST):
        ac_r = execute_accession_flow(page, entry)
        if ac_r["error_found"]:
            pytest.fail(f"[{pid}] Accession: {ac_r['error_message']}")
        assert ac_r["completed"]

Report data consumed by PatientPhaseHtmlGenerator in reporting.py:
    phase_tracker.get_report_data()
    -> { test_name: { patient_id: [PhaseEntry, ...] } }

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, List


# =============================================================================
# STATUS CONSTANTS
# =============================================================================

PASSED       = "PASSED"
FAILED       = "FAILED"
NOT_EXECUTED = "NOT EXECUTED"


# =============================================================================
# ARTIFACT NAMING MAPS
# =============================================================================

#: _FLOW_SHORT is derived from FLOW_REGISTRY (single source of truth).
#: Kept as a module-level dict for fast lookup; populated on first import.
from utils.reporting.constants import FLOW_REGISTRY as _FLOW_REGISTRY
from utils.failure_artifact import write_highlight_sidecar
_FLOW_SHORT: Dict[str, str] = {k: v["short"] for k, v in _FLOW_REGISTRY.items()}

#: Maps lowercase phase-name keywords to descriptive issue-type suffixes.
_PHASE_ISSUE: Dict[str, str] = {
    "front desk":        "regissue",
    "phlebotomist":      "collectissue",
    "accession":         "acceptissue",
    "lab technician":    "labissue",
    "doctor":            "docissue",
    "published reports": "publishissue",
    "recollect":         "recollectissue",
    "reassign":          "reassignissue",
}


def _short_flow(test_name: str) -> str:
    """Return compact, filesystem-safe flow key for artifact naming."""
    return _FLOW_SHORT.get(
        test_name,
        re.sub(r"[^a-z0-9]", "", test_name.lower()),
    )


def _short_phase(phase_name: str) -> str:
    """Return compact, filesystem-safe phase key for artifact naming."""
    return re.sub(r"[^a-z0-9]", "", phase_name.lower())


def _issue_type(phase_name: str) -> str:
    """Map a phase name to a descriptive issue-type suffix (failure artifacts)."""
    pl = phase_name.lower()
    for keyword, issue in _PHASE_ISSUE.items():
        if keyword in pl:
            return issue
    return "failissue"


# =============================================================================
# DATA MODEL
# =============================================================================

@dataclass
class PhaseEntry:
    """Execution result for one phase of one patient in one test."""

    patient_id:      str
    phase_name:      str
    status:          str    # PASSED | FAILED | NOT EXECUTED
    error:           str   = ""
    screenshot_path: str   = ""
    timestamp:       str   = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


# =============================================================================
# PHASE TRACKER
# =============================================================================

class PhaseTracker:
    """
    Session-scoped, in-memory tracker for per-patient, per-phase results.

    Data model:
        _data[test_name][patient_id]  ->  list[PhaseEntry]  (execution order)
        _phase_order[test_name]       ->  list[str]         (phase names, first-seen order)
        _patient_order[test_name]     ->  list[str]         (patient IDs, first-seen order)
        _fail_seq                     ->  dict              (failure sequence counters)

    Artifact sections:
        artifacts/success/   — one screenshot per PASSED phase
        artifacts/failures/  — one screenshot per FAILED phase (named by convention)
    """

    def __init__(self) -> None:
        self._data:          Dict[str, Dict[str, List[PhaseEntry]]] = {}
        self._phase_order:   Dict[str, List[str]]                   = {}
        self._patient_order: Dict[str, List[str]]                   = {}
        self._fail_seq:      Dict[str, int]                         = {}

    # ------------------------------------------------------------------
    # Context manager: wraps one phase block inside a test function
    # ------------------------------------------------------------------

    @contextmanager
    def track(
        self,
        page,
        patient_id: str,
        phase_name: str,
        test_name:  str = "default",
    ) -> Generator[None, None, None]:
        """
        Context manager that auto-records phase outcome and captures artifacts.

        Success path → screenshot in artifacts/success/, marks PASSED.
        Failure path → screenshot in artifacts/failures/ (named by convention),
                       marks FAILED, re-raises so pytest catches the failure.
        Unvisited phases → resolved as NOT EXECUTED at report-generation time.
        """
        self._register(test_name, patient_id, phase_name)
        try:
            yield
            # ── Success path ────────────────────────────────────────────
            shot = self._success_screenshot(page, patient_id, phase_name, test_name)
            self._record(test_name, patient_id, PhaseEntry(
                patient_id=patient_id,
                phase_name=phase_name,
                status=PASSED,
                screenshot_path=shot,
            ))
        except BaseException as exc:
            # ── Failure path ────────────────────────────────────────────
            shot = self._failure_screenshot(page, patient_id, phase_name, test_name)
            self._record(test_name, patient_id, PhaseEntry(
                patient_id=patient_id,
                phase_name=phase_name,
                status=FAILED,
                error=str(exc)[:400],
                screenshot_path=shot,
            ))
            raise

    # ------------------------------------------------------------------
    # Report data access
    # ------------------------------------------------------------------

    def get_report_data(self) -> Dict[str, Dict[str, List[PhaseEntry]]]:
        """
        Return fully resolved report data, grouped by test then patient.

        Schema:
            {
                test_name: {
                    patient_id: [PhaseEntry, ...]  # one per phase in _phase_order
                }
            }

        Phases not recorded for a patient (because test aborted earlier) are
        filled in as NOT EXECUTED entries automatically.
        """
        result: Dict[str, Dict[str, List[PhaseEntry]]] = {}
        for test_name, patient_map in self._data.items():
            phases   = self._phase_order.get(test_name, [])
            patients = self._patient_order.get(test_name, [])
            result[test_name] = {}
            for pid in patients:
                recorded: Dict[str, PhaseEntry] = {
                    e.phase_name: e for e in patient_map.get(pid, [])
                }
                resolved: List[PhaseEntry] = []
                for phase in phases:
                    if phase in recorded:
                        resolved.append(recorded[phase])
                    else:
                        resolved.append(PhaseEntry(
                            patient_id=pid,
                            phase_name=phase,
                            status=NOT_EXECUTED,
                        ))
                result[test_name][pid] = resolved
        return result

    def test_names(self) -> List[str]:
        """All tracked test names in order of first appearance."""
        return list(self._data.keys())

    def phases_for_test(self, test_name: str) -> List[str]:
        """Phase names for *test_name* in execution order."""
        return list(self._phase_order.get(test_name, []))

    def patients_for_test(self, test_name: str) -> List[str]:
        """Patient IDs for *test_name* in order of first appearance."""
        return list(self._patient_order.get(test_name, []))

    def has_data(self) -> bool:
        """True if at least one phase has been tracked."""
        return bool(self._data)

    def merge_serialised(self, payload: Dict[str, Dict[str, List[dict]]]) -> None:
        """Merge a serialised phase_data dict (from another worker) into this tracker.

        Payload shape: {test_name: {patient_id: [PhaseEntry-as-dict, ...]}}.
        Each parallel xdist invocation routes any given test to a single
        worker, so test_names from different workers are disjoint. Within a
        merged test_name, patient_ids are also disjoint. Phase order is
        rebuilt from the entries themselves.
        """
        allowed = set(PhaseEntry.__dataclass_fields__.keys())
        for test_name, patient_map in (payload or {}).items():
            for pid, entries in (patient_map or {}).items():
                for d in entries or []:
                    if not isinstance(d, dict):
                        continue
                    entry = PhaseEntry(**{k: v for k, v in d.items() if k in allowed})
                    self._register(test_name, pid, entry.phase_name)
                    self._record(test_name, pid, entry)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register(
        self, test_name: str, patient_id: str, phase_name: str
    ) -> None:
        """Initialise tracking structures on first encounter."""
        if test_name not in self._data:
            self._data[test_name]          = {}
            self._phase_order[test_name]   = []
            self._patient_order[test_name] = []

        if patient_id not in self._data[test_name]:
            self._data[test_name][patient_id] = []
            self._patient_order[test_name].append(patient_id)

        if phase_name not in self._phase_order[test_name]:
            self._phase_order[test_name].append(phase_name)

    def _record(
        self, test_name: str, patient_id: str, entry: PhaseEntry
    ) -> None:
        """Append a PhaseEntry to the data store."""
        self._data[test_name][patient_id].append(entry)

    def _next_fail_seq(self, pid: str, flow: str, phase: str) -> int:
        """
        Increment and return the failure sequence counter for this
        (patient, flow, phase) combination within the current session.

        The counter ensures unique file names when the same phase is
        retried or re-entered multiple times in one session.
        """
        key = f"{pid}-{flow}-{phase}"
        self._fail_seq[key] = self._fail_seq.get(key, 0) + 1
        return self._fail_seq[key]

    # ── Artifact: FAILURE screenshot ───────────────────────────────────

    def _failure_screenshot(
        self,
        page,
        patient_id: str,
        phase_name: str,
        test_name:  str,
    ) -> str:
        """
        Capture a full-page screenshot on phase failure.

        Naming  : {pid}-{flow}-{phase}-{issuetype}{seq}.png
        Example : p2-e2eb1accession-accession-acceptissue1.png
        Saved to: artifacts/failures/
        """
        try:
            pid_s   = re.sub(r"[^a-z0-9]", "", str(patient_id).lower())
            flow_s  = _short_flow(test_name)
            phase_s = _short_phase(phase_name)
            issue   = _issue_type(phase_name)
            seq     = self._next_fail_seq(pid_s, flow_s, phase_s)
            fname   = f"{pid_s}-{flow_s}-{phase_s}-{issue}{seq}.png"
            dest    = Path("artifacts") / "failures"
            dest.mkdir(parents=True, exist_ok=True)
            path    = dest / fname
            page.screenshot(path=str(path), full_page=True)
            write_highlight_sidecar(page, str(path))
            return str(path)
        except Exception:
            return ""

    # ── Artifact: SUCCESS screenshot ───────────────────────────────────

    @staticmethod
    def _success_screenshot(
        page,
        patient_id: str,
        phase_name: str,
        test_name:  str,
    ) -> str:
        """
        Capture a full-page screenshot on phase success.

        Naming  : {pid}-{flow}-{phase}.png
        Example : p1-e2eacceptance-accession.png
        Saved to: artifacts/success/
        """
        try:
            pid_s   = re.sub(r"[^a-z0-9]", "", str(patient_id).lower())
            flow_s  = _short_flow(test_name)
            phase_s = _short_phase(phase_name)
            fname   = f"{pid_s}-{flow_s}-{phase_s}.png"
            dest    = Path("artifacts") / "success"
            dest.mkdir(parents=True, exist_ok=True)
            path    = dest / fname
            page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            return ""


# =============================================================================
# MODULE-LEVEL SINGLETON
# (imported by conftest.py and all e2e test files)
# =============================================================================

phase_tracker = PhaseTracker()
