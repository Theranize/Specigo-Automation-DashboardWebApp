# -*- coding: utf-8 -*-
"""Root conftest: marker registration, fixture imports, trace management, and report generation."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from fixtures.browser_fixtures import browser_instance, page
from fixtures.session_fixtures import login_as
from fixtures.data_fixtures import (
    login_credentials,
    front_desk_patient_data,
    front_desk_test_payment_data,
    phlebotomist_actions_data,
    accession_actions_data,
    labtech_search_data,
    labtech_tests_data,
    doctor_actions_data,
    reassignment_actions_data,
    doctor_rectify_actions_data,
)

from utils.reporting import (
    SUMMARY_HTML,
    SUMMARY_JSON,
    SUMMARY_CSV,
    ALLURE_RESULTS_DIR,
    ALLURE_HTML_DIR,
    PATIENT_PHASE_HTML,
    PATIENT_PHASE_JSON,
    SCREENSHOTS_SUCCESS_DIR,
    SCREENSHOTS_FAILURES_DIR,
    SESSIONS_PER_BATCH,
    artifact_manager,
    html_generator,
    json_generator,
    csv_generator,
    report_registry,
    phase_html_generator,
    phase_json_generator,
    stakeholder_html_generator,
    stakeholder_pdf_generator,
    save_run_snapshot,
    register_session,
    get_batch_number,
    resolve_report_paths,
    REPORTS_ROOT,
)
from utils.error_detector import detect_ui_errors
from utils.phase_tracker import phase_tracker
from state import runtime_state

HTML_REPORT_PATH = SUMMARY_HTML
JSON_REPORT_PATH = SUMMARY_JSON

_SESSION_START_ISO: str = ""

# stash keys for inter-hook state (pytest 7+ stash API)
_KEY_FAILED     = pytest.StashKey[bool]()
_KEY_START_TIME = pytest.StashKey[float]()
_KEY_SCREENSHOT = pytest.StashKey[str]()
_KEY_VIDEO_PAGE = pytest.StashKey[object]()


# --- CLI options ---

def pytest_addoption(parser: pytest.Parser) -> None:
    """Register --env CLI option for environment selection."""
    parser.addoption(
        "--env",
        action="store",
        default="dev",
        choices=["dev", "staging"],
        help="Target environment: dev (default) or staging",
    )


# --- marker registration ---

def pytest_configure(config: pytest.Config) -> None:
    """Register all custom test markers."""
    _MARKERS = [
        "smoke: Quick smoke tests",
        "regression: Role-wise regression tests",
        "e2e: End-to-end workflow tests",
        "acceptance: Happy path acceptance flows",
        "rejection: Rejection and recollection flows",
        "labtech: Lab technician report entry tests",
        "doctor: Doctor report review tests",
        "rectification: Flows that include a doctor rectify phase",
    ]
    for marker in _MARKERS:
        config.addinivalue_line("markers", marker)


# --- session lifecycle ---

def pytest_sessionstart(session: pytest.Session) -> None:
    """Record session start time and create all artifact/report directories."""
    global _SESSION_START_ISO
    _SESSION_START_ISO = datetime.now().isoformat(timespec="seconds")
    artifact_manager.ensure_dirs()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Generate all reports after the test session completes."""
    results   = report_registry.results()
    summary   = report_registry.summary()
    run_id    = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    start_iso = _SESSION_START_ISO

    phase_data = phase_tracker.get_report_data() if phase_tracker.has_data() else {}

    session_num = register_session(run_id, summary, results, start_iso)
    batch       = get_batch_number(session_num)

    print("")
    print("=" * 66)
    print("  [SESSION SYSTEM]  Session #{} registered successfully.".format(session_num))
    print("  Batch {} of reports  (sessions {}-{}).".format(
        batch, (batch - 1) * 10 + 1, batch * 10
    ))
    print("  Run ID   : {}".format(run_id))
    print("  Started  : {}   Ended: {}".format(
        start_iso, summary.get("generated_at", "?")))
    tests_run = sorted({
        (r.get("test_name") if isinstance(r, dict) else getattr(r, "test_name", ""))
        for r in results
    } - {""})
    print("  Tests    : {}".format(", ".join(tests_run) or "(none)"))
    print("=" * 66)

    save_run_snapshot(run_id, summary, results, session_num, phase_data)

    s_html, s_json, s_csv, ph_html, ph_json = resolve_report_paths(batch)

    html_generator.generate(results, summary, s_html)
    json_generator.generate(results, summary, s_json)
    csv_generator.generate(results, s_csv)

    if phase_tracker.has_data():
        phase_html_generator.generate(
            phase_tracker, ph_html,
            current_session_num=session_num,
            batch=batch,
        )
        phase_json_generator.generate(phase_tracker, ph_json)
        print("  [SESSION SYSTEM]  Phase report (Session {}) -> {}".format(session_num, ph_html))

    print("  [SESSION SYSTEM]  Summary report (Batch {})          -> {}".format(batch, s_html))

    stakeholder_html_path, stakeholder_pdf_path, stakeholder_pdf_ok = _generate_stakeholder_report(
        results, summary, run_id, phase_data
    )

    allure_ok = _run_allure_generate()
    _print_summary(
        summary, allure_ok, s_html, s_json, s_csv, ph_html, session_num, batch,
        stakeholder_html=stakeholder_html_path,
        stakeholder_pdf=stakeholder_pdf_path,
        stakeholder_pdf_ok=stakeholder_pdf_ok,
    )


def _generate_stakeholder_report(results, summary, run_id, phase_data=None):
    """Render the manager-facing HTML + PDF report. Never fails the session."""
    out_dir  = REPORTS_ROOT / "stakeholder"
    run_html = out_dir / f"{run_id}.html"
    run_pdf  = out_dir / f"{run_id}.pdf"
    latest_html = out_dir / "latest.html"
    latest_pdf  = out_dir / "latest.pdf"

    try:
        stakeholder_html_generator.generate(results, summary, run_html, phase_data=phase_data)
        shutil.copy2(run_html, latest_html)
    except Exception as exc:
        print(f"  [STAKEHOLDER] HTML skipped: {exc}")
        return None, None, False

    pdf_ok = stakeholder_pdf_generator.generate(run_html, run_pdf)
    if pdf_ok:
        try:
            shutil.copy2(run_pdf, latest_pdf)
        except OSError as exc:
            print(f"  [STAKEHOLDER] latest.pdf copy skipped: {exc}")

    return latest_html, (latest_pdf if pdf_ok else None), pdf_ok


def _run_allure_generate() -> bool:
    """Run `allure generate` to build an HTML report; returns True on success."""
    allure_bin = shutil.which("allure") or shutil.which("allure.bat")

    if not allure_bin:
        # common Windows install locations (Chocolatey, Scoop, direct download)
        _candidates = [
            r"C:\ProgramData\chocolatey\bin\allure.bat",
            r"C:\ProgramData\chocolatey\bin\allure.cmd",
            r"C:\ProgramData\scoop\shims\allure.bat",
            r"C:\tools\allure\bin\allure.bat",
            r"C:\allure\bin\allure.bat",
        ]
        for c in _candidates:
            if Path(c).exists():
                allure_bin = c
                break

    if not allure_bin:
        print("")
        print("  [allure generate] SKIPPED -- allure CLI not found in PATH.")
        print("  Install: https://allurereport.org/docs/gettingstarted-installation/")
        print("  Then run manually:")
        print("    allure generate {} -o {} --clean".format(
            ALLURE_RESULTS_DIR, ALLURE_HTML_DIR))
        return False

    results_dir = str(ALLURE_RESULTS_DIR)
    html_dir    = str(ALLURE_HTML_DIR)
    cmd         = [allure_bin, "generate", results_dir, "-o", html_dir, "--clean"]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            print("")
            print("  [allure generate] OK -> {}".format(html_dir))
            print("  Open: {}/index.html".format(html_dir))
            return True
        else:
            print("")
            print("  [allure generate] FAILED (exit {})".format(proc.returncode))
            if proc.stderr:
                print("  {}".format(proc.stderr.strip()[:300]))
            return False
    except subprocess.TimeoutExpired:
        print("  [allure generate] TIMEOUT (120s) -- run manually")
        return False
    except Exception as exc:
        print("  [allure generate] ERROR: {}".format(exc))
        return False


def _print_summary(
    summary:             dict,
    allure_generated:    bool           = False,
    summary_html:        Optional[Path] = None,
    summary_json:        Optional[Path] = None,
    summary_csv:         Optional[Path] = None,
    phase_html:          Optional[Path] = None,
    session_num:         int            = 0,
    batch:               int            = 1,
    stakeholder_html:    Optional[Path] = None,
    stakeholder_pdf:     Optional[Path] = None,
    stakeholder_pdf_ok:  bool           = False,
) -> None:
    """Print a concise session summary banner to stdout."""
    s_html  = summary_html or SUMMARY_HTML
    s_json  = summary_json or SUMMARY_JSON
    s_csv   = summary_csv  or SUMMARY_CSV
    ph_html = phase_html   or PATIENT_PHASE_HTML

    sep         = "-" * 66
    pr          = summary.get("pass_rate", 0)
    allure_html = "{}/index.html".format(ALLURE_HTML_DIR) if allure_generated else "(not generated)"
    phase_line  = (
        "    Phase Report (Session {}) -> {}".format(session_num, ph_html)
        if phase_tracker.has_data() else
        "    Phase Report -> (no phase data recorded)"
    )
    batch_note = (
        "  Batch {} of reports (sessions {}-{})".format(
            batch,
            (batch - 1) * SESSIONS_PER_BATCH + 1,
            batch * SESSIONS_PER_BATCH,
        )
    )
    lines = [
        "",
        sep,
        "  TEST SESSION COMPLETE  (Session #{})".format(session_num) if session_num else "  TEST SESSION COMPLETE",
        batch_note,
        "  Passed : {:4}  Failed : {:4}  Errors : {:4}  Skipped: {:4}  Pass Rate: {}%".format(
            summary["passed"],
            summary["failed"],
            summary["errors"],
            summary["skipped"],
            pr,
        ),
        "  Total  : {}   Duration: {}s".format(
            summary["total"], summary["duration_seconds"]
        ),
        "  Summary Reports:",
        "    HTML -> {}".format(s_html),
        "    JSON -> {}".format(s_json),
        "    CSV  -> {}".format(s_csv),
        phase_line,
        "  Stakeholder Report:",
        "    HTML -> {}".format(stakeholder_html or "(not generated)"),
        "    PDF  -> {}".format(stakeholder_pdf or "(not generated)"),
        "  Allure Report:",
        "    Results -> {}  (raw)".format(ALLURE_RESULTS_DIR),
        "    HTML    -> {}  (open in browser)".format(allure_html),
        "  Other Reports:",
        "    Pytest HTML -> reports/html/pytest_report.html",
        "    Pytest JSON -> reports/json/pytest_report.json",
        "  Artifacts:",
        "    Success  -> {}  ({{pid}}-{{flow}}-{{phase}}.png)".format(SCREENSHOTS_SUCCESS_DIR),
        "    Failures -> {}  ({{pid}}-{{flow}}-{{phase}}-{{issue}}{{seq}}.png)".format(SCREENSHOTS_FAILURES_DIR),
        "    Traces   -> artifacts/traces/",
        "    Videos   -> artifacts/videos/  ({patient}-{flowname}.webm)",
        sep,
        "",
    ]
    for line in lines:
        print(line)


# --- per-test trace and timing ---

@pytest.fixture(autouse=True)
def _trace_and_timing(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Record timing, start Playwright trace, save video and trace on teardown."""
    request.node.stash[_KEY_START_TIME] = time.monotonic()

    context    = None
    tracing_on = False
    try:
        bi      = request.getfixturevalue("browser_instance")
        context = bi.get("context") if isinstance(bi, dict) else None
    except pytest.FixtureLookupError:
        pass

    _pg = None
    try:
        _pg = request.getfixturevalue("page")
        request.node.stash[_KEY_VIDEO_PAGE] = _pg
    except pytest.FixtureLookupError:
        pass

    if context:
        try:
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            tracing_on = True
        except Exception:
            pass  # tracing already active or unavailable

    yield

    failed = request.node.stash.get(_KEY_FAILED, False)

    # retain trace zip on failure, discard on pass
    if context and tracing_on:
        if failed:
            t_path = artifact_manager.trace_path(_sanitize(request.node.name))
            try:
                context.tracing.stop(path=str(t_path))
            except Exception:
                _silent(context.tracing.stop)
        else:
            _silent(context.tracing.stop)

    # save video as {patient}-{flowname}.webm for every test
    _pg = request.node.stash.get(_KEY_VIDEO_PAGE, None)
    if _pg is not None:
        try:
            video = _pg.video
        except Exception:
            video = None
        if video is not None:
            patient, flowname = _extract_video_name_parts(request)
            v_dest = artifact_manager.video_path(patient, flowname)
            try:
                video.save_as(str(v_dest))
            except Exception:
                try:
                    staging = video.path()
                    if staging and Path(staging).exists():
                        Path(staging).unlink(missing_ok=True)
                except Exception:
                    pass


# --- failure screenshot and report hook ---

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo,
) -> Generator[None, None, None]:
    """Capture screenshot on failure and register result in ReportRegistry."""
    outcome = yield
    rep     = outcome.get_result()

    # process only the 'call' phase (actual test body)
    if rep.when != "call":
        return

    start    = item.stash.get(_KEY_START_TIME, None)
    duration = round(time.monotonic() - start, 2) if start is not None else 0.0

    test_name  = item.name
    module     = _extract_module(item)
    patient_id = _extract_patient_id(item)

    if rep.skipped:
        status, error_text = "SKIP", "---"
    elif rep.failed:
        status     = "FAIL"
        error_text = _extract_error(rep)
        item.stash[_KEY_FAILED] = True
    else:
        status, error_text = "PASS", "---"

    screenshot_path = "---"
    if rep.failed:
        pg = item.funcargs.get("page")
        if pg:
            screenshot_path = _capture_failure_screenshots(
                pg, test_name, patient_id, error_text, item
            )

    report_registry.add(
        test_name=test_name,
        module=module,
        patient_id=patient_id,
        status=status,
        error=error_text,
        screenshot_path=screenshot_path,
        duration=duration,
    )


# --- screenshot capture ---

def _capture_failure_screenshots(
    page,
    test_name:  str,
    patient_id: str,
    error_text: str,
    item:       pytest.Item,
) -> str:
    """Capture primary + optional UI-error screenshot; return primary path."""
    step         = _failure_step(error_text)
    primary_path = "---"

    try:
        shot_p = artifact_manager.screenshot_path(test_name, patient_id, step)
        page.screenshot(path=str(shot_p), full_page=True)
        primary_path = str(shot_p)
        item.stash[_KEY_SCREENSHOT] = primary_path
    except Exception:
        pass

    try:
        ui_err = detect_ui_errors(page)
        if ui_err:
            ui_p = artifact_manager.screenshot_path(test_name, patient_id, "ui_error")
            page.screenshot(path=str(ui_p), full_page=True)
            if primary_path == "---":
                primary_path = str(ui_p)
    except Exception:
        pass

    return primary_path


# --- helpers ---

def _sanitize(name: str) -> str:
    """Strip characters unsafe in filesystem path components."""
    return re.sub(r"[^\w\-]", "_", str(name))


def _extract_module(item: pytest.Item) -> str:
    """Derive a readable module label from the pytest node id."""
    parts = item.nodeid.split("::")
    if parts:
        stem = Path(parts[0]).stem
        name = re.sub(r"^test_", "", stem)
        name = re.sub(r"_(regression|e2e_|smoke)$", "", name)
        return name.replace("_", " ").title()
    if hasattr(item, "module") and item.module:
        return item.module.__name__
    return "Unknown"


def _extract_patient_id(item: pytest.Item) -> str:
    """Resolve patient ID from runtime_state, parametrize bracket, or 'N/A'."""
    pid = runtime_state.get_value("patient_id")
    if pid:
        return str(pid)
    m = re.search(r"\[(.+)\]", item.name)
    return m.group(1) if m else "N/A"


def _extract_error(rep: pytest.TestReport) -> str:
    """Extract a concise (up to 220-char) error summary from a failed report."""
    if not rep.longrepr:
        return "Unknown error"
    text  = str(rep.longrepr)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # prefer the last line containing a known error keyword
    for ln in reversed(lines):
        if any(kw in ln for kw in ("Error:", "assert", "Timeout", "Exception", "FAILED", "Failed:")):
            if not ln.startswith("E     artifacts/") and not ln.startswith("artifacts/"):
                return ln[:220]
    # fallback: last non-path line
    for ln in reversed(lines):
        if not ln.startswith("artifacts/") and not ln.startswith("E     artifacts/"):
            return ln[:220]
    return lines[-1][:220] if lines else "Unknown error"


def _failure_step(error_text: str) -> str:
    """Map error text to a meaningful screenshot file stem."""
    et = error_text.lower()
    if "timeout"    in et: return "timeout_error"
    if "assert"     in et: return "assertion_fail"
    if "navigation" in et: return "navigation_fail"
    if "api"        in et: return "api_error"
    if "popup"      in et: return "popup_error"
    if "modal"      in et: return "modal_error"
    if "validation" in et: return "validation_error"
    return "failure"


def _extract_video_name_parts(request: pytest.FixtureRequest) -> tuple:
    """Derive (patient, flowname) from test node for video naming."""
    node_id    = request.node.nodeid
    path_parts = node_id.replace("\\", "/").split("/")

    # flowname: strip prefixes, drop underscores, append "flow"
    file_seg = path_parts[-1].split("::")[0]
    stem     = Path(file_seg).stem
    name     = re.sub(r"^test_", "", stem)
    name     = re.sub(r"^e2e_", "", name)
    flowname = name.replace("_", "") + "flow"

    # patient: runtime_state first, then parametrize bracket
    patient = runtime_state.get_value("patient_id") or _extract_patient_id(request.node)

    return _sanitize(str(patient)), _sanitize(flowname)


def _silent(fn, *args, **kwargs) -> None:
    """Call fn silently; swallow any exception."""
    try:
        fn(*args, **kwargs)
    except Exception:
        pass
