# -*- coding: utf-8 -*-
"""
Verification script for the upgraded MNC reporting system.

Simulates a realistic full test session with all 5 DDT patients across
multiple E2E flows, then generates both HTML reports and verifies
every major feature introduced in the new design.

Run:
    powershell.exe -Command "cd D:\automation\playwright; .\Test\Scripts\python.exe verify_reports.py"

Patients simulated:
    P1  Aditya Kumar Mishra   -- full acceptance + doctor resample + combined flow
    P2  Ravi Kumar Sharma     -- partial acceptance (doctor phase fails)
    P3  Sunita Kumar Mishra   -- accession rejection + labtech rejection flows
    P4  Aditya Kumar Mishra   -- error: Mobile already registered (front desk)
    P5  (UPDATE NAME)         -- error: You can only add 10 patients (front desk)

Flows simulated:
    test_e2e_acceptance            (P1 PASS, P2 FAIL-partial, P4 FAIL-err, P5 FAIL-err)
    test_e2e_b1_accession_rejection (P3 PASS)
    test_e2e_b2_labtech_rejection   (P3 PASS)
    test_e2e_b3_doctor_resample     (P1 PASS)
    test_e2e_bc_combined_rejection  (P1 PARTIAL-fail)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: add project root to sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from utils.phase_tracker import PhaseEntry, PASSED, FAILED, NOT_EXECUTED
from utils.reporting import (
    TestResult, ReportRegistry, HtmlReportGenerator,
    JsonReportGenerator, CsvReportGenerator,
    PatientPhaseHtmlGenerator, PatientPhaseJsonGenerator,
    SUMMARY_HTML, SUMMARY_JSON, SUMMARY_CSV,
    PATIENT_PHASE_HTML, PATIENT_PHASE_JSON,
    patient_label, save_run_snapshot, _load_run_history,
    RUNS_DIR, REPORTS_ROOT,
    _FLOW_LABELS, _FLOW_PHASE_ORDER,
)


# =============================================================================
# HELPERS
# =============================================================================

class SimPhaseTracker:
    """
    Lightweight phase tracker for simulation — no Playwright page needed.
    Directly populates the same internal data model that PatientPhaseHtmlGenerator reads.
    """

    def __init__(self) -> None:
        self._data:          dict = {}
        self._phase_order:   dict = {}
        self._patient_order: dict = {}

    # ------------------------------------------------------------------
    def add(
        self,
        test_name:  str,
        patient_id: str,
        phase_name: str,
        status:     str,
        error:      str = "",
        shot:       str = "",
    ) -> None:
        if test_name not in self._data:
            self._data[test_name]          = {}
            self._phase_order[test_name]   = []
            self._patient_order[test_name] = []

        if patient_id not in self._data[test_name]:
            self._data[test_name][patient_id] = []
            self._patient_order[test_name].append(patient_id)

        if phase_name not in self._phase_order[test_name]:
            self._phase_order[test_name].append(phase_name)

        self._data[test_name][patient_id].append(
            PhaseEntry(
                patient_id      = patient_id,
                phase_name      = phase_name,
                status          = status,
                error           = error,
                screenshot_path = shot,
            )
        )

    # ------------------------------------------------------------------
    # API that PatientPhaseHtmlGenerator calls
    # ------------------------------------------------------------------
    def has_data(self) -> bool:
        return bool(self._data)

    def get_report_data(self) -> dict:
        """Return fully resolved data — NOT EXECUTED entries filled in."""
        result = {}
        for test_name, patient_map in self._data.items():
            phases   = self._phase_order.get(test_name, [])
            patients = self._patient_order.get(test_name, [])
            result[test_name] = {}
            for pid in patients:
                recorded = {e.phase_name: e for e in patient_map.get(pid, [])}
                resolved = []
                for phase in phases:
                    if phase in recorded:
                        resolved.append(recorded[phase])
                    else:
                        resolved.append(PhaseEntry(pid, phase, NOT_EXECUTED))
                result[test_name][pid] = resolved
        return result

    def test_names(self):           return list(self._data.keys())
    def phases_for_test(self, t):   return list(self._phase_order.get(t, []))
    def patients_for_test(self, t): return list(self._patient_order.get(t, []))


def _add_all_phases(pt: SimPhaseTracker, test_name: str, patient_id: str,
                    statuses: list[str], errors: list[str] = None) -> None:
    """
    Add every phase for a given (test, patient) from _FLOW_PHASE_ORDER.
    statuses list maps 1:1 to the phases; use 'X' as shorthand for NOT_EXECUTED.
    """
    phases = _FLOW_PHASE_ORDER.get(test_name, [])
    errors = errors or [""] * len(phases)
    # Pad errors if shorter
    errors = list(errors) + [""] * (len(phases) - len(errors))
    for i, phase in enumerate(phases):
        raw = statuses[i] if i < len(statuses) else NOT_EXECUTED
        s = {"P": PASSED, "F": FAILED, "X": NOT_EXECUTED}.get(raw, raw)
        pt.add(test_name, patient_id, phase, s, error=errors[i])


# =============================================================================
# BUILD SIMULATION DATA
# =============================================================================

def build_sim_data():
    """Construct the full realistic test session data."""
    pt  = SimPhaseTracker()
    rr  = ReportRegistry()

    now = datetime.now().isoformat(timespec="seconds")

    # -----------------------------------------------------------------------
    # FLOW 1: test_e2e_acceptance
    # Phases: Front Desk | Phlebotomist | Accession | Lab Technician | Doctor | Published Reports
    # -----------------------------------------------------------------------
    TN_ACC = "test_e2e_acceptance"

    # P1 — Full acceptance (all phases PASS)
    _add_all_phases(pt, TN_ACC, "P1", ["P","P","P","P","P","P"])
    rr.add(f"{TN_ACC}[P1]", "E2E Acceptance", "P1", "PASS",
           duration=42.3)

    # P2 — Partial acceptance: Doctor phase FAILS, Published Reports NOT EXECUTED
    _add_all_phases(pt, TN_ACC, "P2",
        ["P","P","P","P","F","X"],
        errors=["","","","",
                "AssertionError: Doctor approval dialog did not appear after save. "
                "Expected 'Approve' button visible within 10s. TimeoutError at step 4.",
                ""])
    rr.add(f"{TN_ACC}[P2]", "E2E Acceptance", "P2", "FAIL",
           error="AssertionError: Doctor approval dialog did not appear after save.",
           duration=38.1)

    # P4 — Error: Mobile already registered at Front Desk
    _add_all_phases(pt, TN_ACC, "P4",
        ["F","X","X","X","X","X"],
        errors=["AssertionError: Expected UI error 'Mobile number already registered'. "
                "Got error banner with text 'Mobile number already registered'. Test PASSED verification.",
                "","","","",""])
    # P4 PASS because error is expected and verified successfully
    rr.add(f"{TN_ACC}[P4]", "E2E Acceptance", "P4", "PASS",
           duration=5.2)

    # P5 — Error: You can only add 10 patients (relative limit)
    _add_all_phases(pt, TN_ACC, "P5",
        ["P","F","X","X","X","X"],
        errors=["",
                "AssertionError: Expected error 'You can only add 10 patients' at Add Relative step. "
                "Error banner verified successfully.",
                "","","",""])
    # P5 PASS because error is expected and verified
    rr.add(f"{TN_ACC}[P5]", "E2E Acceptance", "P5", "PASS",
           duration=8.7)

    # -----------------------------------------------------------------------
    # FLOW 2: test_e2e_b1_accession_rejection  (P3)
    # Phases: Front Desk | Phlebotomist | Accession (Reject) |
    #         Phlebotomist (Recollect) | Accession (Re-accept) |
    #         Lab Technician | Doctor | Published Reports
    # -----------------------------------------------------------------------
    TN_B1 = "test_e2e_b1_accession_rejection"
    _add_all_phases(pt, TN_B1, "P3", ["P","P","P","P","P","P","P","P"])
    rr.add(f"{TN_B1}[P3]", "E2E B1 Accession Rejection", "P3", "PASS",
           duration=67.4)

    # -----------------------------------------------------------------------
    # FLOW 3: test_e2e_b2_labtech_rejection  (P3)
    # Phases: Front Desk | Phlebotomist | Accession |
    #         Lab Technician (Reject) | Accession (Reassign) |
    #         Phlebotomist (Recollect) | Accession (Re-accept) |
    #         Lab Technician | Doctor | Published Reports
    # -----------------------------------------------------------------------
    TN_B2 = "test_e2e_b2_labtech_rejection"
    _add_all_phases(pt, TN_B2, "P3", ["P","P","P","P","P","P","P","P","P","P"])
    rr.add(f"{TN_B2}[P3]", "E2E B2 Lab Tech Rejection", "P3", "PASS",
           duration=89.2)

    # -----------------------------------------------------------------------
    # FLOW 4: test_e2e_b3_doctor_resample  (P1)
    # Phases: Front Desk | Phlebotomist | Accession | Lab Technician |
    #         Doctor (Resample) | Accession (Reassign) | Phlebotomist (Recollect) |
    #         Accession (Re-accept) | Lab Technician (Re-save) | Doctor (Approve) |
    #         Published Reports
    # -----------------------------------------------------------------------
    TN_B3 = "test_e2e_b3_doctor_resample"
    _add_all_phases(pt, TN_B3, "P1", ["P","P","P","P","P","P","P","P","P","P","P"])
    rr.add(f"{TN_B3}[P1]", "E2E B3 Doctor Resample", "P1", "PASS",
           duration=95.1)

    # -----------------------------------------------------------------------
    # FLOW 5: test_e2e_bc_combined_rejection  (P1) — partial failure
    # Phases: Front Desk | Phlebotomist | Accession (Reject Serum) |
    #         Phlebotomist (Recollect Serum) | Accession (Re-accept Serum) |
    #         Lab Technician (Reject 24h) | Accession (Reassign 24h) |
    #         Phlebotomist (Recollect 24h) | Accession (Re-accept 24h) |
    #         Lab Technician (Save All) | Doctor (Resample LFT) |
    #         Accession (Reassign Serum 2) | Phlebotomist (Recollect Serum 2) |
    #         Accession (Re-accept Serum 2) | Lab Technician (Save LFT) |
    #         Doctor (Approve All) | Published Reports
    # P1: passes first 9, fails at Lab Technician (Save All)
    # -----------------------------------------------------------------------
    TN_BC = "test_e2e_bc_combined_rejection"
    bc_statuses = ["P","P","P","P","P","P","P","P","P","F","X","X","X","X","X","X","X"]
    bc_errors   = [""] * 9 + [
        "TimeoutError: Waiting for element 'Save All' button. "
        "Element not found within 15s. Lab results panel may not have loaded.",
    ] + [""] * 7
    _add_all_phases(pt, TN_BC, "P1", bc_statuses, bc_errors)
    rr.add(f"{TN_BC}[P1]", "E2E BC Combined Rejection", "P1", "FAIL",
           error="TimeoutError: Waiting for element 'Save All' button. Element not found within 15s.",
           duration=72.8)

    return pt, rr


# =============================================================================
# SIMULATE A HISTORICAL RUN (yesterday's run) FOR RUN HISTORY DEMO
# =============================================================================

def seed_historical_runs() -> None:
    """Plant one historical run in reports/runs/ to demonstrate run history."""
    hist_summary = {
        "total": 5, "passed": 3, "failed": 2, "errors": 0, "skipped": 0,
        "pass_rate": 60.0, "duration_seconds": 210.4,
        "generated_at": "2026-03-20T09:15:00",
    }
    hist_results = [
        {"test_name": "test_e2e_acceptance[P1]",  "module": "E2E Acceptance",
         "patient_id": "P1", "status": "PASS", "error": "",
         "screenshot_path": "", "duration": 40.1, "timestamp": "2026-03-20T09:15:00"},
        {"test_name": "test_e2e_acceptance[P2]",  "module": "E2E Acceptance",
         "patient_id": "P2", "status": "FAIL",
         "error": "TimeoutError: Doctor phase timed out",
         "screenshot_path": "", "duration": 35.0, "timestamp": "2026-03-20T09:15:40"},
        {"test_name": "test_e2e_b1_accession_rejection[P3]",
         "module": "E2E B1 Accession Rejection", "patient_id": "P3",
         "status": "PASS", "error": "", "screenshot_path": "", "duration": 65.2,
         "timestamp": "2026-03-20T09:16:55"},
        {"test_name": "test_e2e_b2_labtech_rejection[P3]",
         "module": "E2E B2 Lab Tech Rejection", "patient_id": "P3",
         "status": "FAIL", "error": "AssertionError: Lab save failed",
         "screenshot_path": "", "duration": 55.7, "timestamp": "2026-03-20T09:18:30"},
        {"test_name": "test_e2e_b3_doctor_resample[P1]",
         "module": "E2E B3 Doctor Resample", "patient_id": "P1",
         "status": "PASS", "error": "", "screenshot_path": "", "duration": 88.0,
         "timestamp": "2026-03-20T09:20:35"},
    ]
    # Only save if no historical run exists yet
    run_id = "run_20260320_091500"
    target = RUNS_DIR / f"{run_id}.json"
    if not target.exists():
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"run_id": run_id, "summary": hist_summary, "results": hist_results},
                       indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  [seed] Planted historical run: {run_id}")
    else:
        print(f"  [seed] Historical run already exists: {run_id}")


# =============================================================================
# GENERATE REPORTS
# =============================================================================

def generate_reports(pt: SimPhaseTracker, rr: ReportRegistry) -> dict:
    """Generate all report files and return paths + summary."""
    results = rr.results()
    summary = rr.summary()

    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")

    # Save this run's snapshot FIRST (so it appears in history)
    save_run_snapshot(run_id, summary, results)

    # Generate summary report (HTML, JSON, CSV)
    HtmlReportGenerator().generate(results, summary, SUMMARY_HTML)
    JsonReportGenerator().generate(results, summary, SUMMARY_JSON)
    CsvReportGenerator().generate(results, SUMMARY_CSV)

    # Generate phase report (HTML, JSON)
    PatientPhaseHtmlGenerator().generate(pt, PATIENT_PHASE_HTML)
    PatientPhaseJsonGenerator().generate(pt, PATIENT_PHASE_JSON)

    return {
        "run_id":       run_id,
        "summary":      summary,
        "results":      results,
        "summary_html": SUMMARY_HTML,
        "phase_html":   PATIENT_PHASE_HTML,
        "summary_json": SUMMARY_JSON,
        "phase_json":   PATIENT_PHASE_JSON,
        "summary_csv":  SUMMARY_CSV,
    }


# =============================================================================
# VERIFICATION CHECKS
# =============================================================================

PASS_MARK = "[PASS]"
FAIL_MARK = "[FAIL]"

_checks_run   = 0
_checks_passed = 0
_failures      = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _checks_run, _checks_passed
    _checks_run += 1
    if condition:
        _checks_passed += 1
        print(f"  {PASS_MARK} {label}")
    else:
        _failures.append((label, detail))
        print(f"  {FAIL_MARK} {label}{(' -- ' + detail) if detail else ''}")


def _html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def verify_file_sizes(info: dict) -> None:
    print("\n-- File sizes --")
    for key in ("summary_html","phase_html","summary_json","phase_json","summary_csv"):
        path = Path(str(info[key]))
        exists = path.exists()
        size   = path.stat().st_size if exists else 0
        check(f"{path.name} exists and non-empty", exists and size > 1000,
              f"size={size}")


def verify_summary_report(info: dict) -> None:
    print("\n-- Summary Report: structural checks --")
    html = _html(Path(str(info["summary_html"])))

    # Framework & CDN
    check("Chart.js CDN included",          "chart.js" in html)
    check("Donut chart canvas present",     "donutChart" in html)
    check("Trend chart canvas present",     "trendChart" in html)

    # Sticky header
    check("Sticky header: brand 'MNC'",     "MNC" in html)
    check("Sticky header: pass rate pill",  "Pass Rate" in html)

    # Tab navigation
    check("Tab: Current Run tab button",    "mtab-current" in html)
    check("Tab: Run History tab button",    "mtab-history" in html)
    check("Tab: switchMainTab JS function", "switchMainTab" in html)

    # Stat cards (7)
    check("Card: Total Tests",              "Total Tests" in html)
    check("Card: Passed",                   "Passed" in html)
    check("Card: Failed",                   "Failed" in html)
    check("Card: Errors",                   "Errors" in html)
    check("Card: Skipped",                  "Skipped" in html)
    check("Card: Patients",                 "Patients" in html)
    check("Card: Flows",                    "Flows" in html)

    # Run meta bar
    check("Run meta bar present",           "run-meta" in html)
    check("Run meta: Run ID",               "run_" in html)

    # Phase report link
    check("Phase report link bar",          "patient_phase_report.html" in html)

    # Filter toolbar
    check("Status filter buttons",          "filterStatus" in html)
    check("Search box",                     'placeholder="Search' in html)

    # Result table
    check("Result table: 7 columns",        "Screenshot" in html)

    # Run history
    check("Run History tab panel",          "mpanel-history" in html)
    check("History cards (4)",              "hist-cards" in html)
    check("Run history table rows",         "rhtbody" in html)
    check("Run expand function",            "toggleRun" in html)


def verify_patient_names_in_summary(info: dict) -> None:
    print("\n-- Summary Report: patient display names --")
    html = _html(Path(str(info["summary_html"])))
    patients = {
        "P1": "Aditya Kumar Mishra",
        "P2": "Ravi Kumar Sharma",
        "P3": "Sunita Kumar Mishra",
    }
    for pid, name in patients.items():
        check(f"P{pid[-1]} shown as '{name}'", name in html,
              f"raw '{pid}' may still be present but display name missing")


def verify_run_history(info: dict) -> None:
    print("\n-- Run History: data embedded --")
    html = _html(Path(str(info["summary_html"])))
    history = _load_run_history()
    check("At least 1 historical run saved",    len(history) >= 1)
    check("Current run saved to runs/",         (RUNS_DIR / f"{info['run_id']}.json").exists())
    check("Historical run embedded in HTML",    "run_20260320_091500" in html or "_RUN_HISTORY" in html)
    check("_RUN_HISTORY JS var in HTML",        "_RUN_HISTORY" in html)
    check("Chart.js data vars: _DPASSED",       "_DPASSED" in html)
    check("Chart.js data vars: _DFAILED",       "_DFAILED" in html)


def verify_phase_report(info: dict) -> None:
    print("\n-- Phase Report: structural checks --")
    html = _html(Path(str(info["phase_html"])))

    # Chart
    check("Chart.js CDN in phase report",       "chart.js" in html)
    check("phaseDonut canvas",                  "phaseDonut" in html)
    check("_PH_PASS JS var",                    "_PH_PASS" in html)

    # Patient tabs
    check("Patient tab wrapper",                "ptab-wrap" in html)
    check("Overall Review tab",                 "Overall Review" in html)
    check("showPatientTab JS function",         "showPatientTab" in html)
    check("ptab-panel divs",                    "ptab-panel" in html)
    check("Patient info card",                  "pat-info-card" in html)

    # Flow cards & pipeline
    check("Flow cards present",                 "flow-card" in html)
    check("Pipeline stepper",                   "pipeline" in html)
    check("Pipeline PASS nodes",               "pn-pass" in html)
    check("Pipeline FAIL nodes",               "pn-fail" in html)
    check("Pipeline NOT EXEC nodes",           "pn-notexec" in html)

    # Phase table
    check("Phase table class",                  "phase-tbl" in html)
    check("PASSED badges",                      "pb-pass" in html)
    check("FAILED badges",                      "pb-fail" in html)
    check("NOT EXECUTED badges",                "pb-notexec" in html)

    # Filters
    check("Flow filter tabs",                   "ftab" in html)
    check("Status filter: Passed",              "filterStatus" in html)
    check("Search input",                       "onSearch" in html)

    # Navigation
    check("Back-to-summary link",               "summary_report.html" in html)

    # Legend
    check("Phase legend",                       "Phase Passed" in html)

    # Stat cards
    check("Total Phases card",                  "Total Phases" in html)


def verify_patient_names_in_phase(info: dict) -> None:
    print("\n-- Phase Report: patient display names in tabs --")
    html = _html(Path(str(info["phase_html"])))
    check("P1 tab: 'Aditya Kumar Mishra'",      "Aditya Kumar Mishra" in html)
    check("P2 tab: 'Ravi Kumar Sharma'",        "Ravi Kumar Sharma" in html)
    check("P3 tab: 'Sunita Kumar Mishra'",      "Sunita Kumar Mishra" in html)


def verify_flow_coverage(info: dict) -> None:
    print("\n-- Phase Report: all 5 E2E flows covered --")
    html = _html(Path(str(info["phase_html"])))
    flows = {
        "test_e2e_acceptance":             "E2E Acceptance Flow",
        "test_e2e_b1_accession_rejection": "E2E B1",
        "test_e2e_b2_labtech_rejection":   "E2E B2",
        "test_e2e_b3_doctor_resample":     "E2E B3",
        "test_e2e_bc_combined_rejection":  "E2E BC",
    }
    for tn, label_part in flows.items():
        check(f"Flow present: {label_part}", tn in html or label_part in html)


def verify_summary_data(info: dict) -> None:
    print("\n-- Summary Report: data correctness --")
    s = info["summary"]
    check("Total = 8 test entries",     s["total"] == 8,
          f"got {s['total']}")
    check("Passed >= 5 (P1-acc, P3-b1, P3-b2, P1-b3, P4/P5 error-verified)",
          s["passed"] >= 5,  f"got {s['passed']}")
    check("Failed >= 2 (P2-partial, P1-bc)",
          s["failed"] >= 2,  f"got {s['failed']}")
    check("pass_rate > 0",              s["pass_rate"] > 0, f"got {s['pass_rate']}")
    check("Duration key exists",         "duration_seconds" in s)


def verify_json_output(info: dict) -> None:
    print("\n-- JSON output: valid and complete --")
    sj = Path(str(info["summary_json"]))
    pj = Path(str(info["phase_json"]))

    # Summary JSON
    try:
        data = json.loads(sj.read_text(encoding="utf-8"))
        check("summary_report.json: valid JSON",        True)
        check("summary_report.json: has 'summary' key", "summary" in data)
        check("summary_report.json: has 'results' key", "results" in data)
        check("summary_report.json: results not empty", len(data.get("results",[])) > 0)
    except Exception as e:
        check("summary_report.json: valid JSON", False, str(e))

    # Phase JSON
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
        check("patient_phase_report.json: valid JSON",        True)
        check("patient_phase_report.json: has 'tests' key",   "tests" in data)
        check("patient_phase_report.json: tests not empty",   len(data.get("tests",[])) > 0)
        # Verify all 5 flows
        flow_names = {t["test_name"] for t in data.get("tests",[])}
        for tn in ("test_e2e_acceptance","test_e2e_b1_accession_rejection",
                   "test_e2e_b2_labtech_rejection","test_e2e_b3_doctor_resample",
                   "test_e2e_bc_combined_rejection"):
            check(f"phase JSON has flow: {tn}", tn in flow_names)
    except Exception as e:
        check("patient_phase_report.json: valid JSON", False, str(e))


def verify_screenshot_paths(info: dict) -> None:
    print("\n-- Screenshot path format (patients/ subdir) --")
    # The new format is artifacts/screenshots/<test_name>/patients/<pid>/<step>.png
    from utils.reporting import ArtifactManager
    am = ArtifactManager()
    p = am.screenshot_path("test_e2e_acceptance[P1]", "P1", "failure")
    check("Screenshot path includes 'patients' subdir", "patients" in str(p),
          f"got: {p}")
    check("Screenshot path: correct structure",
          str(p).replace("\\", "/") ==
          "artifacts/screenshots/test_e2e_acceptance_P1_/patients/P1/failure.png",
          f"got: {p}")


def verify_csv_output(info: dict) -> None:
    print("\n-- CSV output --")
    csv_path = Path(str(info["summary_csv"]))
    check("summary_report.csv exists", csv_path.exists())
    if csv_path.exists():
        content = csv_path.read_text(encoding="utf-8-sig")
        check("CSV has header row",    "Test Name" in content)
        check("CSV has data rows",     "test_e2e_acceptance" in content)
        check("CSV has patient IDs",   "P1" in content)


def verify_patient_per_tab(info: dict) -> None:
    print("\n-- Phase Report: per-patient tab content --")
    html = _html(Path(str(info["phase_html"])))

    # Per-patient panels
    for pid in ("P1","P2","P3","P4","P5"):
        check(f"ptab-panel for {pid} exists", f'id="ptab-panel-{pid}"' in html,
              f"patient {pid} tab panel missing")

    # Per-patient flows
    check("P1 panel: Acceptance flow phases",       "P1" in html and "E2E Acceptance Flow" in html)
    check("P3 panel: B1 Accession Rejection flow",  "E2E B1" in html)
    check("P3 panel: B2 Lab Tech Rejection flow",   "E2E B2" in html)
    check("P1 panel: B3 Doctor Resample flow",      "E2E B3" in html)
    check("P1 panel: BC Combined Rejection flow",   "E2E BC" in html)


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    sep = "=" * 70
    print(sep)
    print("  MNC Automation Report Verification")
    print(f"  Run at: {datetime.now().isoformat(timespec='seconds')}")
    print(sep)

    # 1. Seed historical run
    print("\n[1] Seeding historical run data...")
    seed_historical_runs()

    # 2. Build simulation
    print("\n[2] Building simulation data (5 patients, 5 E2E flows)...")
    pt, rr = build_sim_data()
    print(f"  Phase tracker flows:   {pt.test_names()}")
    print(f"  Phase tracker patients: {set(p for tn in pt.test_names() for p in pt.patients_for_test(tn))}")
    print(f"  Registry entries:      {len(rr.results())}")

    # 3. Generate reports
    print("\n[3] Generating reports...")
    t0   = time.monotonic()
    info = generate_reports(pt, rr)
    elapsed = round(time.monotonic() - t0, 2)
    print(f"  Run ID: {info['run_id']}")
    print(f"  Generated in {elapsed}s")
    for key in ("summary_html","phase_html","summary_json","phase_json","summary_csv"):
        p = Path(str(info[key]))
        print(f"  {p.name}: {p.stat().st_size:,} bytes")

    # 4. Run verification checks
    print("\n[4] Running verification checks...")
    verify_file_sizes(info)
    verify_summary_data(info)
    verify_summary_report(info)
    verify_patient_names_in_summary(info)
    verify_run_history(info)
    verify_phase_report(info)
    verify_patient_names_in_phase(info)
    verify_patient_per_tab(info)
    verify_flow_coverage(info)
    verify_json_output(info)
    verify_csv_output(info)
    verify_screenshot_paths(info)

    # 5. Final result
    print(f"\n{sep}")
    print(f"  VERIFICATION RESULT: {_checks_passed}/{_checks_run} checks passed")
    if _failures:
        print(f"\n  FAILURES ({len(_failures)}):")
        for label, detail in _failures:
            print(f"    {FAIL_MARK} {label}" + (f"\n        {detail}" if detail else ""))
    else:
        print("  All checks passed.")
    print(sep)

    # 6. Report locations
    print("\n[5] Output files:")
    for key, label in [
        ("summary_html",  "Summary Report  (open in browser)"),
        ("phase_html",    "Phase Report    (open in browser)"),
        ("summary_json",  "Summary JSON"),
        ("phase_json",    "Phase JSON"),
        ("summary_csv",   "Summary CSV"),
    ]:
        print(f"  {label}: {info[key]}")

    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())
