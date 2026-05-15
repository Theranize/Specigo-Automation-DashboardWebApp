# -*- coding: utf-8 -*-
"""Root conftest: marker registration, fixture imports, trace management, and report generation."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from fixtures.browser_fixtures import browser_instance, page
from fixtures.session_fixtures import login_as
from flows.logout_flow import execute_logout
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
    save_run_snapshot,
    register_session,
    load_session_registry,
    get_batch_number,
    resolve_report_paths,
)
from utils.error_detector import detect_ui_errors
from utils.failure_artifact import write_highlight_sidecar
from utils.phase_tracker import phase_tracker
from state import runtime_state

HTML_REPORT_PATH = SUMMARY_HTML
JSON_REPORT_PATH = SUMMARY_JSON

_SESSION_START_ISO: str = ""

# Visual hold (seconds) between a test finishing and the per-test browser
# closing — gives the operator a chance to see the final page state, and on
# failure follows the post-logout idle screen.
POST_TEST_HOLD_SECONDS: float = 3.0

# Where xdist workers dump their per-process result/phase partials so the
# master can absorb them at sessionfinish.
_PARTIALS_DIR: Path = Path("reports") / "runs" / "_partials"


def _is_xdist_worker(session_or_config) -> bool:
    """True when running inside an xdist worker (has a `workerinput` dict)."""
    cfg = getattr(session_or_config, "config", session_or_config)
    return getattr(cfg, "workerinput", None) is not None


def _is_xdist_master(session_or_config) -> bool:
    """True for non-xdist runs and for the xdist coordinator process."""
    return not _is_xdist_worker(session_or_config)


def _dump_worker_partial(worker_id: str) -> None:
    """Serialise this worker's results + phase data to a JSON partial file."""
    try:
        _PARTIALS_DIR.mkdir(parents=True, exist_ok=True)
        results = [asdict(r) for r in report_registry.results()]
        phase_payload: dict = {}
        if phase_tracker.has_data():
            for tn, pmap in phase_tracker.get_report_data().items():
                phase_payload[tn] = {
                    pid: [asdict(e) for e in entries]
                    for pid, entries in pmap.items()
                }
        payload = {"results": results, "phase_data": phase_payload}
        (_PARTIALS_DIR / f"{worker_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        print(f"  [xdist] worker {worker_id} failed to dump partial: {exc}")


def _absorb_worker_partials() -> None:
    """Read every worker partial, fold into master singletons, then unlink."""
    if not _PARTIALS_DIR.exists():
        return
    for f in sorted(_PARTIALS_DIR.glob("*.json")):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
            report_registry.extend_from_dicts(payload.get("results") or [])
            phase_tracker.merge_serialised(payload.get("phase_data") or {})
        except Exception as exc:
            print(f"  [xdist] could not absorb partial '{f.name}': {exc}")
        finally:
            try:
                f.unlink()
            except OSError:
                pass

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

    # ── Super-user (admin/manager) CLI options ──────────────────────────────
    # All five default to None/False so they have zero effect on existing tests.
    # The super-user entry test (tests/e2e/super_user/test_super_user_e2e.py)
    # parametrizes only when --super-targets is set — otherwise it collects
    # nothing and discovery is unchanged.
    parser.addoption("--super-as",
        action="store", default=None, choices=["admin", "manager"],
        help="Super-user role driving the run (admin|manager)")
    parser.addoption("--super-targets",
        action="store", default=None,
        help="Comma-separated patient IDs (P1..P14) for the super-user run")
    parser.addoption("--super-until",
        action="store", default=None, choices=["fd", "phlebo", "acc", "labt", "doc"],
        help="Super-user stop stage (`till X`)")
    parser.addoption("--super-continue",
        action="store_true", default=False,
        help="Hand off to per-role users after super-user's stop stage")
    parser.addoption("--super-continue-till",
        action="store", default=None, choices=["fd", "phlebo", "acc", "labt", "doc"],
        help="Cap stage for the per-role continuation (`continue till Y`)")
    parser.addoption("--super-reassign",
        action="store", default="default", choices=["default", "super", "users"],
        help="Reassign/recollect ownership override "
             "(super = +reassign-admin, users = +reassign-users)")


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
    _validate_super_user_options(config)


# --- Same-mobile concurrent execution ---
# Tests sharing a backend mobile (e.g. P1/P2/P3/P4/P6/P12/P13 all on Aditya
# 7777777777) used to serialise through a `_mobile_serialise` autouse fixture
# wrapping `mobile_lock` (utils/login_lock.py). That left workers idle for
# ~28 min while one worker drained the Aditya queue (autouse fixtures run
# BEFORE the browser fixture, so blocked workers had no browser open).
#
# We now allow concurrent same-mobile execution and rely on each phase
# disambiguating *its own* report by the unique sample_id captured from the
# FD barcode modal (`runtime_state.add_sample` in `flows/front_desk_flow.py`):
#   - phlebo/accession `find_sample_block` already match by sample_id
#   - doctor `open_report_entry` matches by sample_id (fallback rows.first)
#   - accession `find_sample_block_by_name` (recollection) takes a
#     `preferred_sample_id` hint
# Login serialisation (`login_lock`) is unchanged — still required to
# prevent the dev backend rejecting concurrent same-role logins.
# `mobile_lock` and `mobile_for` remain available as utilities for any
# narrowly-scoped future use, but are not currently wired into any fixture.


def _validate_super_user_options(config: pytest.Config) -> None:
    """Parse-time validation for super-user CLI options.

    Rejects `till X continue till Y` when canonical order of Y < X. Also
    rejects --super-targets without --super-as (and vice versa) so misuse
    fails fast instead of silently collecting nothing.
    """
    targets = config.getoption("--super-targets", default=None)
    super_as = config.getoption("--super-as", default=None)
    if bool(targets) ^ bool(super_as):
        raise pytest.UsageError(
            "Super-user mode requires both --super-as and --super-targets"
        )
    if not targets:
        return
    until      = config.getoption("--super-until", default=None)
    cont_till  = config.getoption("--super-continue-till", default=None)
    has_cont   = config.getoption("--super-continue", default=False)
    order = {"fd": 1, "phlebo": 2, "acc": 3, "labt": 4, "doc": 5}
    if cont_till and not has_cont:
        raise pytest.UsageError(
            "--super-continue-till requires --super-continue"
        )
    if until and cont_till and order[cont_till] < order[until]:
        raise pytest.UsageError(
            f"--super-continue-till ({cont_till}) must be at or after "
            f"--super-until ({until}) in canonical order fd→phlebo→acc→labt→doc"
        )


# --- session lifecycle ---

def pytest_sessionstart(session: pytest.Session) -> None:
    """Record session start time and create all artifact/report directories."""
    global _SESSION_START_ISO
    if _is_xdist_master(session):
        _SESSION_START_ISO = datetime.now().isoformat(timespec="seconds")
    artifact_manager.ensure_dirs()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Generate all reports after the test session completes.

    Under xdist: each worker dumps its partial state and returns early.
    Master absorbs every partial into the singletons before running the
    existing report-generation flow, so the summary covers all workers.
    """
    if _is_xdist_worker(session):
        _dump_worker_partial(session.config.workerinput["workerid"])
        return

    _absorb_worker_partials()

    results          = report_registry.results()
    summary          = report_registry.summary()
    next_session_num = load_session_registry().get("total_sessions", 0) + 1
    run_id           = f"Run_Sp_{next_session_num:010d}"
    start_iso        = _SESSION_START_ISO

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

    html_generator.generate(results, summary, s_html, run_id=run_id)
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

    allure_ok = _run_allure_generate()
    _print_summary(
        summary, allure_ok, s_html, s_json, s_csv, ph_html, session_num, batch,
    )


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

    # Per-test cleanup: on failure attempt an explicit logout while the page
    # is still open, then hold the final state briefly before the browser
    # tears down (browser_instance is function-scoped, so close happens next).
    if failed and _pg is not None:
        try:
            if not _pg.is_closed():
                execute_logout(_pg)
        except Exception:
            pass  # best-effort; the next test gets a fresh browser regardless
    try:
        time.sleep(POST_TEST_HOLD_SECONDS)
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
        write_highlight_sidecar(page, str(shot_p))
        primary_path = str(shot_p)
        item.stash[_KEY_SCREENSHOT] = primary_path
    except Exception:
        pass

    try:
        ui_err = detect_ui_errors(page)
        if ui_err:
            ui_p = artifact_manager.screenshot_path(test_name, patient_id, "ui_error")
            page.screenshot(path=str(ui_p), full_page=True)
            write_highlight_sidecar(page, str(ui_p))
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
