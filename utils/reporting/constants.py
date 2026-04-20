# -*- coding: utf-8 -*-
"""
Path constants, batch settings, and FLOW_REGISTRY for the reporting package.

FLOW_REGISTRY is the single source of truth for all E2E flow metadata — label,
filesystem-safe short key, and ordered phase list.  Adding a new E2E test means
adding one entry here; no other file needs editing.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List


# =============================================================================
# PATHS
# =============================================================================
ARTIFACTS_ROOT    = Path("artifacts")
REPORTS_ROOT      = Path("reports")

SCREENSHOTS_DIR          = ARTIFACTS_ROOT / "screenshots"
SCREENSHOTS_SUCCESS_DIR  = ARTIFACTS_ROOT / "success"
SCREENSHOTS_FAILURES_DIR = ARTIFACTS_ROOT / "failures"
TRACES_DIR               = ARTIFACTS_ROOT / "traces"
LOGS_DIR                 = ARTIFACTS_ROOT / "logs"
VIDEOS_DIR               = ARTIFACTS_ROOT / "videos"

HTML_REPORT_DIR    = REPORTS_ROOT / "html"
JSON_REPORT_DIR    = REPORTS_ROOT / "json"
ALLURE_RESULTS_DIR = REPORTS_ROOT / "allure-results"
ALLURE_HTML_DIR    = REPORTS_ROOT / "allure-report"
RUNS_DIR              = REPORTS_ROOT / "runs"
SESSION_REGISTRY_PATH = REPORTS_ROOT / "session_registry.json"
SESSIONS_PER_BATCH    = 10          # rotate to a new report file after this many sessions

SUMMARY_HTML = REPORTS_ROOT / "summary_report.html"
SUMMARY_JSON = REPORTS_ROOT / "summary_report.json"
SUMMARY_CSV  = REPORTS_ROOT / "summary_report.csv"

PATIENT_PHASE_HTML = REPORTS_ROOT / "patient_phase_report.html"
PATIENT_PHASE_JSON = REPORTS_ROOT / "patient_phase_report.json"

# Aliases kept for backward compatibility
HTML_REPORT_PATH = SUMMARY_HTML
JSON_REPORT_PATH = SUMMARY_JSON


# =============================================================================
# FLOW REGISTRY  –  single source of truth for all E2E flows
# =============================================================================
#: Adding a new test:  append one dict here; no other file needs editing.
FLOW_REGISTRY: Dict[str, Dict] = {
    "test_e2e_acceptance": {
        "label":       "E2E Acceptance Flow",
        "short":       "e2eacceptance",
        "phase_order": [
            "Front Desk", "Phlebotomist", "Accession",
            "Lab Technician", "Doctor", "Published Reports",
        ],
    },
}


def flow_label(test_name: str) -> str:
    """Return human-readable label for a test; falls back to title-cased name."""
    return FLOW_REGISTRY.get(test_name, {}).get(
        "label", test_name.replace("_", " ").title()
    )


def flow_short(test_name: str) -> str:
    """Return compact filesystem-safe key for a test."""
    short = FLOW_REGISTRY.get(test_name, {}).get("short", "")
    return short or re.sub(r"[^a-z0-9]", "", test_name.lower())


def flow_phase_order(test_name: str) -> List[str]:
    """Return ordered phase list for a test (empty list if unknown)."""
    return list(FLOW_REGISTRY.get(test_name, {}).get("phase_order", []))


# =============================================================================
# PATIENT DISPLAY NAMES  –  lazy-loaded on first call to patient_label()
# =============================================================================
_PATIENT_DISPLAY: Dict[str, str] = {}
_PATIENT_DISPLAY_LOADED: bool = False


def _load_patient_display_names() -> Dict[str, str]:
    """Load {patient_id_ref: display_name} from test_data/front_desk/patient_data.json."""
    try:
        path = Path("test_data/front_desk/patient_data.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        result: Dict[str, str] = {}
        for p in data.get("patients", []):
            pid = p.get("patient_id_ref", "").strip()
            dn  = p.get("patient_intent", {}).get("card_display_name", "").strip()
            if not dn or "UPDATE" in dn.upper():
                pt    = p.get("patient", {})
                parts = [pt.get("first_name", ""), pt.get("middle_name", ""), pt.get("last_name", "")]
                dn    = " ".join(x for x in parts if x).strip()
            if pid:
                result[pid] = dn or pid
        return result
    except Exception:
        return {}


def patient_label(pid: str) -> str:
    """Return human-readable display name for a patient ID, falling back to the ID itself."""
    global _PATIENT_DISPLAY, _PATIENT_DISPLAY_LOADED
    if not _PATIENT_DISPLAY_LOADED:
        _PATIENT_DISPLAY = _load_patient_display_names()
        _PATIENT_DISPLAY_LOADED = True
    return _PATIENT_DISPLAY.get(str(pid), str(pid))
