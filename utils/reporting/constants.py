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
# Standard 5-phase pipeline — used by full-acceptance-style tests.
_STD_ACCEPTANCE: List[str] = [
    "Front Desk", "Phlebotomist", "Accession",
    "Lab Technician", "Doctor",
]

# Standard 3-cycle rejection pipeline — Acc reject -> recollect -> re-accept,
# LT reject -> recollect -> re-accept, then Doctor resample -> re-cycle ->
# final approval. Concrete sample names (Serum / Urine / 24h / WB / etc.) are
# captured per-test below; the structural shape is constant.
_REJECTION_3CYCLE_TEMPLATE: List[str] = [
    "Front Desk", "Phlebotomist",
    "Accession (Reject {a})", "Phlebotomist (Recollect {a})", "Accession (Re-accept {a})",
    "Lab Technician (Reject {b})",
    "Accession (Reassign {b})", "Phlebotomist (Recollect {b})", "Accession (Re-accept {b})",
    "Lab Technician (Save All)",
    "Doctor (Resample {c})",
    "Accession (Reassign {d})", "Phlebotomist (Recollect {d})", "Accession (Re-accept {d})",
    "Lab Technician (Save {c})",
    "Doctor ({final} {c})",
]


def _rejection_3cycle(a: str, b: str, c: str, d: str, final: str) -> List[str]:
    """Materialise the 3-cycle rejection phase-order template with concrete sample names."""
    return [p.format(a=a, b=b, c=c, d=d, final=final) for p in _REJECTION_3CYCLE_TEMPLATE]


FLOW_REGISTRY: Dict[str, Dict] = {
    # ── Acceptance flows ──────────────────────────────────────────────────
    "test_e2e_acceptance": {
        "label":       "E2E Acceptance Flow",
        "short":       "e2eacceptance",
        "phase_order": _STD_ACCEPTANCE + ["Published Reports"],
    },
    "test_e2e_p3_partial_approve": {
        "label":       "P3 Partial Approve",
        "short":       "e2ep3partial",
        "phase_order": _STD_ACCEPTANCE,
    },
    "test_e2e_p4_rectification": {
        "label":       "P4 Rectification",
        "short":       "e2ep4rectify",
        "phase_order": [
            "Front Desk", "Phlebotomist", "Accession", "Lab Technician",
            "Doctor (Approve)", "Doctor (Rectify)",
        ],
    },
    "test_e2e_p5_relative_acceptance": {
        "label":       "P5 Relative Acceptance",
        "short":       "e2ep5relative",
        "phase_order": _STD_ACCEPTANCE,
    },
    "test_e2e_p7_limit_error": {
        "label":       "P7 Add-Relative Limit",
        "short":       "e2ep7limit",
        "phase_order": ["Front Desk"],
    },
    "test_e2e_p8_new_patient_acceptance": {
        "label":       "P8 New Patient Acceptance",
        "short":       "e2ep8newaccept",
        "phase_order": _STD_ACCEPTANCE,
    },
    # NOTE: file name is `test_e2e_p10_duplicate_mobile_error.py` but the
    # `_TEST` constant inside the file (which phase_tracker keys by) is
    # `test_e2e_p11_duplicate_mobile_error`. The registry key MUST match
    # `_TEST` so flow_phase_order() resolves correctly in the phase report.
    "test_e2e_p11_duplicate_mobile_error": {
        "label":       "P11 Duplicate Mobile",
        "short":       "e2ep11dupmobile",
        "phase_order": ["Front Desk"],
    },
    "test_e2e_p12_relative_acceptance": {
        "label":       "P12 New Relative + Rectify",
        "short":       "e2ep12relrectify",
        "phase_order": _STD_ACCEPTANCE,
    },
    "test_e2e_p14_partial_approve": {
        "label":       "P14 Partial Approve",
        "short":       "e2ep14partial",
        "phase_order": [
            "Front Desk", "Phlebotomist", "Accession", "Lab Technician",
            "Doctor (Partial Approve)",
        ],
    },

    # ── Rejection flows ───────────────────────────────────────────────────
    "test_e2e_p2_rejection": {
        "label":       "P2 3-Cycle Rejection",
        "short":       "e2ep2rejection",
        "phase_order": _rejection_3cycle("Serum", "24h", "LFT", "Serum 2", "Partial Approve"),
    },
    "test_e2e_p6_rejection": {
        "label":       "P6 3-Cycle Rejection",
        "short":       "e2ep6rejection",
        "phase_order": _rejection_3cycle("Urine", "Serum", "CBC", "WB", "Approve"),
    },
    "test_e2e_p9_new_patient_rejection": {
        "label":       "P9 New Patient Rejection",
        "short":       "e2ep9newreject",
        "phase_order": _rejection_3cycle("Serum", "24h", "LFT", "Serum 2", "Approve"),
    },
    "test_e2e_p10_new_patient_partial": {
        "label":       "P10 New Patient Partial + Rectify",
        "short":       "e2ep10newpartial",
        "phase_order": [
            "Front Desk", "Phlebotomist",
            "Accession (Reject 24h)", "Phlebotomist (Recollect 24h)", "Accession (Re-accept 24h)",
            "Lab Technician",
            "Doctor (Approve)", "Doctor (Rectify LFT)",
        ],
    },
    "test_e2e_p13_partial_rejection": {
        "label":       "P13 Partial Rejection",
        "short":       "e2ep13partialreject",
        "phase_order": [
            "Front Desk", "Phlebotomist",
            "Accession (Reject Serum)", "Phlebotomist (Recollect Serum)", "Accession (Re-accept Serum)",
            "Lab Technician (Reject 24h)",
            "Accession (Reassign 24h)", "Phlebotomist (Recollect 24h)", "Accession (Re-accept 24h)",
            "Lab Technician (Save All)",
            "Doctor (Approve All)",
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
