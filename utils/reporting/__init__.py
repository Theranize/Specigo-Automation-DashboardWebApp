# -*- coding: utf-8 -*-
"""
utils.reporting — public API for the reporting package.

Re-exports every symbol that conftest.py (and any other caller) previously
imported from the monolithic utils/reporting.py.  Import paths are unchanged:

    from utils.reporting import report_registry, html_generator, ...
"""
from __future__ import annotations

# --- paths / constants ---
from utils.reporting.constants import (
    SUMMARY_HTML,
    SUMMARY_JSON,
    SUMMARY_CSV,
    PATIENT_PHASE_HTML,
    PATIENT_PHASE_JSON,
    ALLURE_RESULTS_DIR,
    ALLURE_HTML_DIR,
    SCREENSHOTS_SUCCESS_DIR,
    SCREENSHOTS_FAILURES_DIR,
    SESSION_REGISTRY_PATH,
    SESSIONS_PER_BATCH,
    ARTIFACTS_ROOT,
    REPORTS_ROOT,
    SCREENSHOTS_DIR,
    TRACES_DIR,
    LOGS_DIR,
    VIDEOS_DIR,
    HTML_REPORT_DIR,
    JSON_REPORT_DIR,
    RUNS_DIR,
    HTML_REPORT_PATH,
    JSON_REPORT_PATH,
    FLOW_REGISTRY,
    flow_label,
    flow_short,
    flow_phase_order,
    patient_label,
)

# --- data model ---
from utils.reporting.models import TestResult, _EMPTY

# --- session helpers ---
from utils.reporting.session import (
    save_run_snapshot,
    _load_run_history,
    load_session_registry,
    register_session,
    get_batch_number,
    resolve_report_paths,
    load_batch_sessions,
)

# --- singletons ---
from utils.reporting.singletons import (
    artifact_manager,
    report_registry,
    html_generator,
    json_generator,
    csv_generator,
    phase_html_generator,
    phase_json_generator,
    stakeholder_html_generator,
    stakeholder_pdf_generator,
)

__all__ = [
    # paths / constants
    "SUMMARY_HTML", "SUMMARY_JSON", "SUMMARY_CSV",
    "PATIENT_PHASE_HTML", "PATIENT_PHASE_JSON",
    "ALLURE_RESULTS_DIR", "ALLURE_HTML_DIR",
    "SCREENSHOTS_SUCCESS_DIR", "SCREENSHOTS_FAILURES_DIR",
    "SESSION_REGISTRY_PATH", "SESSIONS_PER_BATCH",
    "ARTIFACTS_ROOT", "REPORTS_ROOT",
    "SCREENSHOTS_DIR", "TRACES_DIR", "LOGS_DIR", "VIDEOS_DIR",
    "HTML_REPORT_DIR", "JSON_REPORT_DIR", "RUNS_DIR",
    "HTML_REPORT_PATH", "JSON_REPORT_PATH",
    "FLOW_REGISTRY", "flow_label", "flow_short", "flow_phase_order",
    "patient_label",
    # data model
    "TestResult", "_EMPTY",
    # session helpers
    "save_run_snapshot", "_load_run_history", "load_session_registry",
    "register_session", "get_batch_number", "resolve_report_paths",
    "load_batch_sessions",
    # singletons
    "artifact_manager", "report_registry",
    "html_generator", "json_generator", "csv_generator",
    "phase_html_generator", "phase_json_generator",
    "stakeholder_html_generator", "stakeholder_pdf_generator",
]
