# -*- coding: utf-8 -*-
"""
Summary report utilities: registry, artifact path management,
and HTML / JSON / CSV report generation.

Produces these report files after each test session:
    reports/summary_report.html      -- Visual dashboard (main report)
    reports/summary_report.json      -- Structured JSON
    reports/summary_report.csv       -- Flat CSV for Excel / CI parsing
    reports/patient_phase_report.html -- E2E phase-level breakdown (4-column + charts)
    reports/patient_phase_report.json -- Structured phase JSON

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import csv as _csv
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html import escape
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional


# =============================================================================
# PATHS
# =============================================================================
ARTIFACTS_ROOT    = Path("artifacts")
REPORTS_ROOT      = Path("reports")

SCREENSHOTS_DIR          = ARTIFACTS_ROOT / "screenshots"
SCREENSHOTS_SUCCESS_DIR  = ARTIFACTS_ROOT / "success"
SCREENSHOTS_FAILURES_DIR = ARTIFACTS_ROOT / "failures"
TRACES_DIR               = ARTIFACTS_ROOT / "traces"
LOGS_DIR          = ARTIFACTS_ROOT / "logs"
VIDEOS_DIR        = ARTIFACTS_ROOT / "videos"

HTML_REPORT_DIR    = REPORTS_ROOT / "html"
JSON_REPORT_DIR    = REPORTS_ROOT / "json"
ALLURE_RESULTS_DIR = REPORTS_ROOT / "allure-results"
ALLURE_HTML_DIR    = REPORTS_ROOT / "allure-report"
RUNS_DIR              = REPORTS_ROOT / "runs"
SESSION_REGISTRY_PATH = REPORTS_ROOT / "session_registry.json"
SESSIONS_PER_BATCH    = 10          # rotate to report N+1 after this many sessions

SUMMARY_HTML = REPORTS_ROOT / "summary_report.html"
SUMMARY_JSON = REPORTS_ROOT / "summary_report.json"
SUMMARY_CSV  = REPORTS_ROOT / "summary_report.csv"

HTML_REPORT_PATH = SUMMARY_HTML
JSON_REPORT_PATH = SUMMARY_JSON


# =============================================================================
# DATA MODEL
# =============================================================================
_EMPTY = ""


@dataclass
class TestResult:
    """Single test result entry for the report table."""
    test_name:       str
    module:          str
    patient_id:      str
    status:          str
    error:           str
    screenshot_path: str
    duration:        float
    timestamp:       str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


# =============================================================================
# PATIENT DISPLAY NAMES
# =============================================================================

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
                parts = [pt.get("first_name",""), pt.get("middle_name",""), pt.get("last_name","")]
                dn    = " ".join(x for x in parts if x).strip()
            if pid:
                result[pid] = dn or pid
        return result
    except Exception:
        return {}

_PATIENT_DISPLAY: Dict[str, str] = _load_patient_display_names()

def patient_label(pid: str) -> str:
    """Return human-readable display name for a patient ID, falling back to ID."""
    return _PATIENT_DISPLAY.get(str(pid), str(pid))


# =============================================================================
# RUN HISTORY
# =============================================================================

def save_run_snapshot(
    run_id:      str,
    summary:     dict,
    results:     list,
    session_num: int  = 0,
    phase_data:  Optional[dict] = None,
) -> None:
    """Persist this run's summary + results + phase data to reports/runs/<run_id>.json."""
    try:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        serialised = [asdict(r) if hasattr(r, "__dataclass_fields__") else dict(r) for r in results]
        # Serialise phase data (PhaseEntry dataclasses → plain dicts)
        ser_phases: dict = {}
        if phase_data:
            for tn, patient_map in phase_data.items():
                ser_phases[tn] = {}
                for pid, entries in patient_map.items():
                    ser_phases[tn][pid] = [
                        asdict(e) if hasattr(e, "__dataclass_fields__") else dict(e)
                        for e in entries
                    ]
        payload = {
            "run_id":      run_id,
            "session_num": session_num,
            "summary":     summary,
            "results":     serialised,
            "phase_data":  ser_phases,
        }
        (RUNS_DIR / f"{run_id}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass

def _load_run_history() -> List[dict]:
    """Load all saved run snapshots in chronological order."""
    if not RUNS_DIR.exists():
        return []
    runs = []
    for f in sorted(RUNS_DIR.glob("run_*.json")):
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return runs


# =============================================================================
# SESSION REGISTRY  –  persistent session counter & metadata
# =============================================================================

def load_session_registry() -> dict:
    """Load the session registry; returns empty structure if file absent/corrupt."""
    if SESSION_REGISTRY_PATH.exists():
        try:
            return json.loads(SESSION_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"total_sessions": 0, "sessions": []}


def register_session(
    run_id:    str,
    summary:   dict,
    results,
    start_iso: str,
) -> int:
    """
    Append a new entry to the session registry and return the new session number.

    Keeps the 'sessions' list as the authoritative ordered record of all runs.
    """
    registry    = load_session_registry()
    session_num = registry["total_sessions"] + 1

    # Derive list of distinct test names executed this session
    tests_executed: List[str] = sorted({
        (r.get("test_name") if isinstance(r, dict) else getattr(r, "test_name", ""))
        for r in results
    } - {""})

    entry: dict = {
        "session_num":      session_num,
        "run_id":           run_id,
        "start_time":       start_iso,
        "end_time":         summary.get("generated_at", ""),
        "duration_seconds": summary.get("duration_seconds", 0),
        "tests_executed":   tests_executed,
        "summary":          summary,
    }
    registry["total_sessions"] = session_num
    registry["sessions"].append(entry)

    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    SESSION_REGISTRY_PATH.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return session_num


def get_batch_number(session_num: int) -> int:
    """Return the 1-based batch index for *session_num* (10 sessions per batch)."""
    return (session_num - 1) // SESSIONS_PER_BATCH + 1


def resolve_report_paths(batch: int) -> tuple:
    """
    Return (summary_html, summary_json, summary_csv, phase_html, phase_json).
    Summary report is cumulative across ALL sessions — always the same file.
    Phase report rotates per batch (batch 1 → default names, batch 2 → suffix 2, etc.).
    """
    s = "" if batch == 1 else str(batch)
    return (
        SUMMARY_HTML,
        SUMMARY_JSON,
        SUMMARY_CSV,
        REPORTS_ROOT / f"patient_phase_report{s}.html",
        REPORTS_ROOT / f"patient_phase_report{s}.json",
    )


def load_batch_sessions(batch: int) -> List[dict]:
    """
    Load all run snapshots that belong to *batch* in session-number order.

    Each returned dict is the full run snapshot augmented with session-registry
    metadata (session_num, start_time, end_time, tests_executed).
    """
    registry = load_session_registry()
    lo = (batch - 1) * SESSIONS_PER_BATCH + 1
    hi = batch * SESSIONS_PER_BATCH

    batch_meta = [
        s for s in registry.get("sessions", [])
        if lo <= s.get("session_num", 0) <= hi
    ]

    result: List[dict] = []
    for meta in batch_meta:
        run_id    = meta.get("run_id", "")
        snap_path = RUNS_DIR / f"{run_id}.json"
        if snap_path.exists():
            try:
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
                # Overlay registry metadata (session_num etc.) onto snapshot
                snap.setdefault("session_num",      meta.get("session_num", 0))
                snap.setdefault("start_time",       meta.get("start_time", ""))
                snap.setdefault("end_time",         meta.get("end_time", ""))
                snap.setdefault("tests_executed",   meta.get("tests_executed", []))
                result.append(snap)
            except Exception:
                pass
        else:
            # Snapshot missing – synthesise from registry metadata only
            fallback = dict(meta)
            fallback.setdefault("phase_data", {})
            fallback.setdefault("results",    [])
            result.append(fallback)
    return result


# =============================================================================
# ARTIFACT MANAGER
# =============================================================================
class ArtifactManager:
    """Manages directory structure and canonical file paths."""

    @staticmethod
    def _sanitize(name: str) -> str:
        return re.sub(r"[^\w\-]", "_", str(name))

    def ensure_dirs(self) -> None:
        for d in (
            SCREENSHOTS_DIR, SCREENSHOTS_SUCCESS_DIR, SCREENSHOTS_FAILURES_DIR,
            TRACES_DIR, LOGS_DIR, VIDEOS_DIR,
            HTML_REPORT_DIR, JSON_REPORT_DIR,
            ALLURE_RESULTS_DIR, ALLURE_HTML_DIR,
            REPORTS_ROOT,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def screenshot_path(self, test_name: str, patient_id: str, step: str) -> Path:
        dest = (
            SCREENSHOTS_DIR
            / self._sanitize(test_name)
            / "patients"
            / self._sanitize(patient_id)
        )
        dest.mkdir(parents=True, exist_ok=True)
        return dest / f"{self._sanitize(step)}.png"

    def trace_path(self, test_name: str) -> Path:
        TRACES_DIR.mkdir(parents=True, exist_ok=True)
        return TRACES_DIR / f"{self._sanitize(test_name)}.zip"

    def log_path(self, test_name: str) -> Path:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return LOGS_DIR / f"{self._sanitize(test_name)}.log"

    def video_path(self, patient: str, flowname: str) -> Path:
        """Return the destination path for a session video.

        Naming format: {patient}-{flowname}.webm
        Example: P1-acceptanceflow.webm, P2-b1accessionrejectionflow.webm
        Overwrites if a file with the same name already exists.
        """
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        name = f"{self._sanitize(patient)}-{self._sanitize(flowname)}.webm"
        return VIDEOS_DIR / name


# =============================================================================
# REPORT REGISTRY
# =============================================================================
class ReportRegistry:
    """Session-scoped in-memory registry for test results."""

    def __init__(self) -> None:
        self._results:    List[TestResult] = []
        self._start_time: float            = time.monotonic()

    def add(
        self,
        test_name:       str,
        module:          str,
        patient_id:      str,
        status:          str,
        error:           str   = _EMPTY,
        screenshot_path: str   = _EMPTY,
        duration:        float = 0.0,
    ) -> None:
        def _norm(v: str) -> str:
            return _EMPTY if v in ("---", "\u2014", "-") else (v or _EMPTY)
        self._results.append(
            TestResult(
                test_name=test_name, module=module, patient_id=patient_id,
                status=status, error=_norm(error),
                screenshot_path=_norm(screenshot_path),
                duration=round(duration, 2),
            )
        )

    def results(self) -> List[TestResult]:
        return list(self._results)

    def summary(self) -> dict:
        total    = len(self._results)
        passed   = sum(1 for r in self._results if r.status == "PASS")
        failed   = sum(1 for r in self._results if r.status == "FAIL")
        errors   = sum(1 for r in self._results if r.status == "ERROR")
        skipped  = sum(1 for r in self._results if r.status == "SKIP")
        elapsed  = round(time.monotonic() - self._start_time, 2)
        pass_pct = round(passed / total * 100, 1) if total else 0.0
        return {
            "total": total, "passed": passed, "failed": failed,
            "errors": errors, "skipped": skipped,
            "pass_rate": pass_pct, "duration_seconds": elapsed,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }


# =============================================================================
# HTML REPORT GENERATOR  (summary_report.html)
# =============================================================================

_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#0d2137;--blue:#1677ff;--green:#389e0d;--red:#cf1322;
  --orange:#d46b08;--purple:#722ed1;--teal:#08979c;--grey:#8c8c8c;
  --bg:#f0f2f5;--surface:#fff;--border:#e8e8e8;
  --text:#1a1a1a;--text2:#595959;--text3:#8c8c8c;
  --r:8px;--sh:0 2px 8px rgba(0,0,0,.08);--sh2:0 4px 16px rgba(0,0,0,.14);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
     background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;padding-bottom:64px}
/* ===== STICKY HEADER ===== */
.hdr{background:var(--navy);color:#fff;height:56px;padding:0 32px;
     display:flex;align-items:center;justify-content:space-between;
     position:sticky;top:0;z-index:500;box-shadow:0 2px 10px rgba(0,0,0,.4)}
.hdr-brand{display:flex;flex-direction:column;gap:1px}
.hdr-brand .logo{font-size:1rem;font-weight:800;letter-spacing:.02em}
.hdr-brand .logo span{color:#4096ff}
.hdr-brand .sub{font-size:.68rem;color:rgba(255,255,255,.42)}
.hdr-right{display:flex;align-items:center;gap:16px}
.hdr-pill{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.09);
          border-radius:20px;padding:4px 14px}
.hp-num{font-size:1.15rem;font-weight:800;line-height:1}
.hp-lbl{font-size:.65rem;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.07em}
.hp-green{color:#73d13d}.hp-yellow{color:#ffd666}.hp-red{color:#ff7875}
.hdr-nav{display:flex;gap:4px}
.hnav-btn{padding:5px 14px;border:none;border-radius:16px;background:transparent;
          color:rgba(255,255,255,.65);cursor:pointer;font-size:.8rem;
          font-family:inherit;transition:all .15s}
.hnav-btn:hover{background:rgba(255,255,255,.1);color:#fff}
.hnav-btn.active{background:rgba(255,255,255,.16);color:#fff;font-weight:600}
/* ===== LAYOUT ===== */
.wrap{max-width:1480px;margin:0 auto;padding:24px 32px}
/* ===== MAIN TABS ===== */
.main-tabs{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:24px}
.main-tab{padding:10px 22px;border:none;background:transparent;cursor:pointer;
          font-size:.86rem;color:var(--text2);font-family:inherit;
          border-bottom:3px solid transparent;margin-bottom:-2px;
          transition:all .15s;display:flex;align-items:center;gap:8px;font-weight:500}
.main-tab:hover{color:var(--blue);background:#f0f5ff}
.main-tab.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:700}
.main-tab .tc{background:#e6f0ff;color:var(--blue);border-radius:10px;
              padding:1px 7px;font-size:.7rem;font-weight:700}
.main-tab.active .tc{background:var(--blue);color:#fff}
.tab-panel{display:none}.tab-panel.active{display:block}
/* ===== RUN META BAR ===== */
.run-meta{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
          padding:11px 20px;margin-bottom:18px;display:flex;align-items:center;
          gap:28px;flex-wrap:wrap;border-left:4px solid var(--blue)}
.rm-item{display:flex;flex-direction:column;gap:0}
.rm-lbl{font-size:.65rem;text-transform:uppercase;letter-spacing:.08em;color:var(--text3)}
.rm-val{font-size:.88rem;font-weight:600;color:var(--text)}
/* ===== STAT CARDS ===== */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));
       gap:12px;margin-bottom:18px}
.card{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
      padding:16px 14px;display:flex;flex-direction:column;align-items:center;
      gap:4px;border-top:3px solid var(--border);
      transition:transform .15s,box-shadow .15s;cursor:default}
.card:hover{transform:translateY(-2px);box-shadow:var(--sh2)}
.card.c-all{border-color:#1677ff}.card.c-pass{border-color:#52c41a}
.card.c-fail{border-color:#ff4d4f}.card.c-err{border-color:#fa8c16}
.card.c-skip{border-color:#d9d9d9}.card.c-pat{border-color:#722ed1}
.card.c-flow{border-color:#13c2c2}
.card .num{font-size:2rem;font-weight:800;line-height:1.1}
.card .lbl{font-size:.66rem;color:var(--text3);text-transform:uppercase;
           letter-spacing:.07em;text-align:center}
.n-blue{color:#1677ff}.n-green{color:#389e0d}.n-red{color:#cf1322}
.n-orange{color:#d46b08}.n-grey{color:#8c8c8c}.n-purple{color:#722ed1}
.n-teal{color:#08979c}
/* ===== CHARTS ROW ===== */
.charts-row{display:grid;grid-template-columns:280px 1fr;gap:16px;margin-bottom:18px}
@media(max-width:820px){.charts-row{grid-template-columns:1fr}}
.chart-card{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
            padding:20px;display:flex;flex-direction:column;gap:10px}
.chart-title{font-size:.72rem;font-weight:700;text-transform:uppercase;
             letter-spacing:.07em;color:var(--text2)}
.chart-wrap{position:relative;width:100%;display:flex;align-items:center;
            justify-content:center;min-height:200px}
/* ===== PHASE LINK BAR ===== */
.phase-link-bar{background:#f0f5ff;border:1px solid #adc6ff;border-radius:var(--r);
                padding:10px 20px;margin-bottom:16px;display:flex;align-items:center;
                justify-content:space-between;font-size:.85rem}
.phase-link-bar a{color:var(--blue);font-weight:600;text-decoration:none;
                  display:inline-flex;align-items:center;gap:5px}
.phase-link-bar a:hover{text-decoration:underline}
/* ===== TOOLBAR ===== */
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.fbtn{padding:5px 14px;border:1px solid var(--border);border-radius:20px;
      background:var(--surface);cursor:pointer;font-size:.79rem;
      color:var(--text2);transition:all .12s;white-space:nowrap;font-family:inherit}
.fbtn:hover{border-color:var(--blue);color:var(--blue)}
.fbtn.active{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600}
.fbtn.fa-pass.active{background:#52c41a;border-color:#52c41a}
.fbtn.fa-fail.active{background:#ff4d4f;border-color:#ff4d4f}
.fbtn.fa-error.active{background:#fa8c16;border-color:#fa8c16}
.fbtn.fa-skip.active{background:#8c8c8c;border-color:#8c8c8c}
.search-box{margin-left:auto;padding:6px 14px;border:1px solid var(--border);
            border-radius:20px;font-size:.82rem;outline:none;
            transition:border-color .12s;min-width:200px;font-family:inherit}
.search-box:focus{border-color:var(--blue);box-shadow:0 0 0 2px rgba(22,119,255,.1)}
/* ===== RESULT TABLE ===== */
.tbl-wrap{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);overflow:hidden}
table{width:100%;border-collapse:collapse}
thead th{background:var(--navy);color:rgba(255,255,255,.85);
         padding:10px 14px;text-align:left;font-size:.7rem;
         text-transform:uppercase;letter-spacing:.07em;
         white-space:nowrap;cursor:pointer;user-select:none}
thead th:hover{background:#1a3550}
thead th .si{margin-left:4px;opacity:.4;font-size:.68rem}
thead th.sorted .si{opacity:1}
tbody td{padding:9px 14px;border-bottom:1px solid #f5f5f5;vertical-align:middle;font-size:.84rem}
tbody tr:last-child td{border-bottom:none}
tbody tr.row-pass:hover{background:#f6ffed}
tbody tr.row-fail{background:#fff2f0}
tbody tr.row-fail:hover{background:#ffe8e6}
tbody tr.row-error{background:#fff7e6}
tbody tr.row-error:hover{background:#fff1d6}
tbody tr.row-skip{background:#fafafa}
tbody tr.row-skip:hover{background:#f5f5f5}
/* ===== BADGES ===== */
.badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;
       border-radius:10px;font-size:.74rem;font-weight:700;white-space:nowrap}
.badge::before{content:'';width:6px;height:6px;border-radius:50%;display:inline-block;flex-shrink:0}
.b-pass{background:#f6ffed;color:#389e0d;border:1px solid #b7eb8f}
.b-pass::before{background:#52c41a}
.b-fail{background:#fff2f0;color:#cf1322;border:1px solid #ffa39e}
.b-fail::before{background:#ff4d4f}
.b-error{background:#fff7e6;color:#d46b08;border:1px solid #ffd591}
.b-error::before{background:#fa8c16}
.b-skip{background:#fafafa;color:#8c8c8c;border:1px solid #d9d9d9}
.b-skip::before{background:#d9d9d9}
/* ===== TABLE CELLS ===== */
.test-cell{font-family:'Consolas','Courier New',monospace;font-size:.8rem;
           color:#262626;max-width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mod-cell{color:var(--text2)}.pid-cell{font-weight:600;color:var(--blue);white-space:nowrap}
.err-cell{color:#cf1322;font-size:.8rem;max-width:220px}
.err-short{cursor:pointer}.err-short:hover{text-decoration:underline dashed}
.err-full{display:none;white-space:pre-wrap;word-break:break-all;font-size:.76rem}
.err-expanded .err-short{display:none}.err-expanded .err-full{display:block}
a.shot-link{color:var(--blue);font-size:.8rem;text-decoration:none;
            display:inline-flex;align-items:center;gap:3px}
a.shot-link:hover{text-decoration:underline}
a.shot-link::before{content:'\\1F4F8';font-size:.75rem}
.dur-cell{white-space:nowrap;color:var(--text2);font-size:.82rem}
.no-data{text-align:center;padding:48px!important;color:var(--text3);font-size:.92rem}
/* ===== RUN HISTORY ===== */
.hist-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));
            gap:12px;margin-bottom:18px}
.hcard{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
       padding:16px 20px;border-left:4px solid var(--border)}
.hcard.hc-total{border-left-color:#1677ff}.hcard.hc-best{border-left-color:#52c41a}
.hcard.hc-last{border-left-color:#722ed1}.hcard.hc-avg{border-left-color:#13c2c2}
.hcard .hnum{font-size:1.7rem;font-weight:800;line-height:1.1}
.hcard .hlbl{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;color:var(--text3)}
.hcard .hsub{font-size:.78rem;color:var(--text2);margin-top:2px}
.run-id-cell{font-family:'Consolas','Courier New',monospace;font-size:.8rem;color:#262626}
.open-btn{padding:4px 12px;background:var(--blue);color:#fff;border:none;
          border-radius:12px;cursor:pointer;font-size:.75rem;font-family:inherit;
          text-decoration:none;display:inline-block;transition:background .12s}
.open-btn:hover{background:#0958d9}
.run-detail-row{display:none;background:#f8faff}
.run-detail-row td{padding:0!important}
.run-detail-inner{padding:14px 20px;font-size:.82rem}
.run-detail-inner table{margin-top:8px;font-size:.8rem}
.run-detail-inner thead th{background:#1a3550;font-size:.68rem}
.run-detail-inner tbody td{padding:7px 12px}
.run-detail-row.open{display:table-row}
/* ===== FOOTER ===== */
.footer{margin-top:28px;text-align:center;font-size:.74rem;color:var(--text3)}
.footer a{color:var(--blue);text-decoration:none}
.footer a:hover{text-decoration:underline}
"""

_JS = """
/* ---- Main tab switching ---- */
function switchMainTab(id) {
  document.querySelectorAll('.main-tab').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.remove('active'); });
  document.getElementById('mtab-' + id).classList.add('active');
  document.getElementById('mpanel-' + id).classList.add('active');
}

/* ---- Current-run table filter ---- */
var _sf = 'ALL', _sq = '';
function applyFilters() {
  var rows = document.querySelectorAll('#rtbody tr');
  rows.forEach(function(r) {
    var b = r.querySelector('.badge');
    var sm = (_sf === 'ALL') || (b && b.getAttribute('data-status') === _sf);
    var qm = !_sq || r.textContent.toLowerCase().indexOf(_sq.toLowerCase()) >= 0;
    r.style.display = (sm && qm) ? '' : 'none';
  });
}
function filterStatus(s) {
  _sf = s;
  document.querySelectorAll('.fbtn').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.getElementById('fb-' + s);
  if (btn) btn.classList.add('active');
  applyFilters();
}
function onSearch(q) { _sq = q; applyFilters(); }

/* ---- Sort current-run table ---- */
var _sc = -1, _sa = true;
function sortCol(c) {
  if (_sc === c) { _sa = !_sa; } else { _sc = c; _sa = true; }
  var tbody = document.getElementById('rtbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a, b) {
    var av = a.cells[c] ? a.cells[c].textContent.trim() : '';
    var bv = b.cells[c] ? b.cells[c].textContent.trim() : '';
    var an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return _sa ? an - bn : bn - an;
    return _sa ? av.localeCompare(bv, undefined, {sensitivity:'base'})
               : bv.localeCompare(av, undefined, {sensitivity:'base'});
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  document.querySelectorAll('thead th .si').forEach(function(si, i) {
    si.innerHTML = i === c ? (_sa ? '&#9650;' : '&#9660;') : '&#8597;';
    si.parentElement.classList.toggle('sorted', i === c);
  });
  applyFilters();
}
function toggleErr(el) { el.closest('.err-cell').classList.toggle('err-expanded'); }

/* ---- History search & session filter ---- */
var _histSess = 0;
var _histQ    = '';
function filterHistSession(snum) {
  _histSess = snum;
  document.querySelectorAll('[id^="hsf-"]').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.getElementById('hsf-' + snum);
  if (btn) btn.classList.add('active');
  _refreshHistTable();
}
function onHistSearch(q) {
  _histQ = q.toLowerCase();
  _refreshHistTable();
}
function _refreshHistTable() {
  document.querySelectorAll('#rhtbody > tr.run-row').forEach(function(r) {
    var matchSess = (_histSess === 0 || parseInt(r.dataset.session || 0) === _histSess);
    var matchQ    = (!_histQ || r.textContent.toLowerCase().indexOf(_histQ) >= 0);
    r.style.display = (matchSess && matchQ) ? '' : 'none';
    var next = r.nextElementSibling;
    if (next && next.classList.contains('run-detail-row')) next.style.display = 'none';
  });
}
/* ---- Run history row expand ---- */
function toggleRun(btn, runIdx) {
  var detailRow = document.getElementById('rdr-' + runIdx);
  if (!detailRow) return;
  var isOpen = detailRow.classList.contains('open');
  document.querySelectorAll('.run-detail-row.open').forEach(function(r) { r.classList.remove('open'); });
  if (!isOpen) {
    detailRow.classList.add('open');
    btn.textContent = 'Close';
  } else {
    btn.textContent = 'Open';
  }
  document.querySelectorAll('.run-row .open-btn').forEach(function(b) {
    if (b !== btn) b.textContent = 'Open';
  });
}

/* ---- Charts (Chart.js) ---- */
document.addEventListener('DOMContentLoaded', function() {
  var donutEl = document.getElementById('donutChart');
  if (donutEl && window.Chart) {
    new Chart(donutEl.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['Passed','Failed','Errors','Skipped'],
        datasets: [{
          data: [_DPASSED, _DFAILED, _DERRORS, _DSKIPPED],
          backgroundColor: ['#52c41a','#ff4d4f','#fa8c16','#d9d9d9'],
          borderWidth: 2, borderColor: '#fff'
        }]
      },
      options: {
        cutout: '68%',
        plugins: {
          legend: { position: 'bottom', labels: { padding: 10, font: { size: 11 } } }
        }
      }
    });
  }
  var trendEl = document.getElementById('trendChart');
  if (trendEl && window.Chart && _RUN_HISTORY.length > 0) {
    var labels = _RUN_HISTORY.map(function(r) {
      return r.session_num ? 'Session ' + r.session_num : (r.run_id || '').replace('run_','').replace(/_/g,' ');
    });
    var rates = _RUN_HISTORY.map(function(r) { return r.summary ? r.summary.pass_rate : 0; });
    var colors = rates.map(function(v) {
      return v >= 90 ? '#52c41a' : (v >= 70 ? '#fa8c16' : '#ff4d4f');
    });
    new Chart(trendEl.getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{ label: 'Pass Rate %', data: rates,
          backgroundColor: colors, borderRadius: 4, borderSkipped: false }]
      },
      options: {
        scales: {
          y: { min: 0, max: 100, ticks: { callback: function(v) { return v + '%'; } } },
          x: { ticks: { font: { size: 10 } } }
        },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            title: function(items) {
              var r = _RUN_HISTORY[items[0].dataIndex];
              var tests = (r.tests_executed || []).join(', ') || '(none)';
              return (r.session_num ? 'Session ' + r.session_num : items[0].label) + ' \u2014 ' + tests;
            },
            label: function(c) { return c.raw + '%'; }
          }}
        }
      }
    });
  }
});
"""


class HtmlReportGenerator:
    """Generates a self-contained HTML dashboard report (summary_report.html)."""

    def generate(
        self,
        results: List[TestResult],
        summary: dict,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self._build(results, summary), encoding="utf-8")

    def _build(self, results: List[TestResult], summary: dict) -> str:
        pr      = summary["pass_rate"]
        pr_cls  = "hp-green" if pr >= 90 else ("hp-yellow" if pr >= 70 else "hp-red")
        total   = summary["total"]
        passed  = summary["passed"]
        failed  = summary["failed"]
        errors  = summary["errors"]
        skipped = summary["skipped"]
        dur     = summary["duration_seconds"]
        gen_at  = summary["generated_at"]

        # Compute run_id from generated_at
        try:
            dt_obj = datetime.fromisoformat(gen_at)
            run_id = dt_obj.strftime("run_%Y%m%d_%H%M%S")
        except Exception:
            run_id = "run_unknown"

        # Unique patients and modules
        unique_patients = len({r.patient_id for r in results if r.patient_id})
        unique_modules  = len({r.module for r in results if r.module})

        # Load run history
        runs = _load_run_history()
        num_runs = len(runs)

        # Rows for current run table
        rows_html = "\n".join(self._row(r) for r in results)
        empty_row = (
            '<tr><td colspan="7" class="no-data">No test results recorded.</td></tr>'
            if not results else ""
        )

        # JS data variables
        js_vars = (
            f"var _DPASSED = {passed};\n"
            f"var _DFAILED = {failed};\n"
            f"var _DERRORS = {errors};\n"
            f"var _DSKIPPED = {skipped};\n"
            f"var _RUN_HISTORY = {json.dumps(runs)};\n"
        )

        # Session filter buttons for run history
        _session_nums = sorted({r.get("session_num", 0) for r in runs if r.get("session_num", 0)})
        if _session_nums:
            _sf_all  = '<button class="fbtn active" id="hsf-0" onclick="filterHistSession(0)">All Sessions</button>'
            _sf_btns = "".join(
                f'<button class="fbtn" id="hsf-{sn}" onclick="filterHistSession({sn})">Session {sn}</button>'
                for sn in _session_nums
            )
            sess_filter_html = _sf_all + _sf_btns
        else:
            sess_filter_html = ""

        # History tab content
        hist_cards_html = self._run_hist_cards(runs)
        hist_table_html = self._run_hist_table(runs, run_id)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Summary Report &mdash; {escape(gen_at[:10])}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>{_CSS}</style>
</head>
<body>

<!-- ===== STICKY HEADER ===== -->
<header class="hdr">
  <div class="hdr-brand">
    <div class="logo">Summary <span>Report</span></div>
    <div class="sub">Test Run Summary &mdash; {escape(gen_at)}</div>
  </div>
  <div class="hdr-right">
    <div class="hdr-pill">
      <div>
        <div class="hp-num {pr_cls}">{pr}%</div>
        <div class="hp-lbl">Pass Rate</div>
      </div>
    </div>
    <nav class="hdr-nav">
      <button class="hnav-btn active" id="mtab-current"
              onclick="switchMainTab('current')">Current Run</button>
      <button class="hnav-btn" id="mtab-history"
              onclick="switchMainTab('history')">Run History ({num_runs})</button>
    </nav>
  </div>
</header>

<div class="wrap">

  <!-- ===== MAIN TABS ===== -->
  <div class="main-tabs">
    <button class="main-tab active" id="mtab-current"
            onclick="switchMainTab('current')">
      Current Run
      <span class="tc">{total}</span>
    </button>
    <button class="main-tab" id="mtab-history"
            onclick="switchMainTab('history')">
      Run History
      <span class="tc">{num_runs}</span>
    </button>
  </div>

  <!-- ===== CURRENT RUN PANEL ===== -->
  <div class="tab-panel active" id="mpanel-current">

    <!-- Run meta bar -->
    <div class="run-meta">
      <div class="rm-item">
        <div class="rm-lbl">Run ID</div>
        <div class="rm-val">{escape(run_id)}</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Date</div>
        <div class="rm-val">{escape(gen_at[:10])}</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Duration</div>
        <div class="rm-val">{dur}s</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Total Tests</div>
        <div class="rm-val">{total}</div>
      </div>
      <div class="rm-item">
        <div class="rm-lbl">Pass Rate</div>
        <div class="rm-val">{pr}%</div>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="cards">
      <div class="card c-all">
        <div class="num n-blue">{total}</div>
        <div class="lbl">Total</div>
      </div>
      <div class="card c-pass">
        <div class="num n-green">{passed}</div>
        <div class="lbl">Passed</div>
      </div>
      <div class="card c-fail">
        <div class="num n-red">{failed}</div>
        <div class="lbl">Failed</div>
      </div>
      <div class="card c-err">
        <div class="num n-orange">{errors}</div>
        <div class="lbl">Errors</div>
      </div>
      <div class="card c-skip">
        <div class="num n-grey">{skipped}</div>
        <div class="lbl">Skipped</div>
      </div>
      <div class="card c-pat">
        <div class="num n-purple">{unique_patients}</div>
        <div class="lbl">Patients</div>
      </div>
      <div class="card c-flow">
        <div class="num n-teal">{unique_modules}</div>
        <div class="lbl">Flows</div>
      </div>
    </div>

    <!-- Charts row -->
    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-title">Result Distribution</div>
        <div class="chart-wrap">
          <canvas id="donutChart" width="220" height="220"></canvas>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title">Pass Rate Trend &mdash; By Session</div>
        <div class="chart-wrap">
          <canvas id="trendChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Phase report link bar -->
    <div class="phase-link-bar">
      <span>E2E phase-level breakdown available in the Phase Report</span>
      <a href="patient_phase_report.html" target="_blank">
        Open Phase Breakdown Report &rarr;
      </a>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <button id="fb-ALL"   class="fbtn active"   onclick="filterStatus('ALL')">
        All ({total})
      </button>
      <button id="fb-PASS"  class="fbtn fa-pass"  onclick="filterStatus('PASS')">
        Pass ({passed})
      </button>
      <button id="fb-FAIL"  class="fbtn fa-fail"  onclick="filterStatus('FAIL')">
        Fail ({failed})
      </button>
      <button id="fb-ERROR" class="fbtn fa-error" onclick="filterStatus('ERROR')">
        Error ({errors})
      </button>
      <button id="fb-SKIP"  class="fbtn fa-skip"  onclick="filterStatus('SKIP')">
        Skip ({skipped})
      </button>
      <input class="search-box" type="text"
             placeholder="Search tests, modules, patients..."
             oninput="onSearch(this.value)">
    </div>

    <!-- Result table -->
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th onclick="sortCol(0)">Test<span class="si">&#8597;</span></th>
            <th onclick="sortCol(1)">Module<span class="si">&#8597;</span></th>
            <th onclick="sortCol(2)">Patient<span class="si">&#8597;</span></th>
            <th onclick="sortCol(3)">Status<span class="si">&#8597;</span></th>
            <th onclick="sortCol(4)">Error<span class="si">&#8597;</span></th>
            <th>Screenshot</th>
            <th onclick="sortCol(6)">Time<span class="si">&#8597;</span></th>
          </tr>
        </thead>
        <tbody id="rtbody">
          {rows_html or empty_row}
        </tbody>
      </table>
    </div>

  </div><!-- #mpanel-current -->

  <!-- ===== RUN HISTORY PANEL ===== -->
  <div class="tab-panel" id="mpanel-history">

    {hist_cards_html}

    <!-- Trend chart in history panel -->
    <div class="charts-row" style="grid-template-columns:1fr">
      <div class="chart-card">
        <div class="chart-title">Pass Rate Trend &mdash; All Sessions</div>
        <div class="chart-wrap" style="min-height:180px">
          <canvas id="trendChartHist"></canvas>
        </div>
      </div>
    </div>

    <!-- History toolbar -->
    <div class="toolbar" style="margin-bottom:14px">
      {sess_filter_html}
      <input class="search-box" type="text"
             placeholder="Search run ID, date..."
             oninput="onHistSearch(this.value)">
    </div>

    <!-- Run history table -->
    <div class="tbl-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Run ID</th>
            <th>Date</th>
            <th>Total</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Pass %</th>
            <th>Duration</th>
            <th>Open</th>
          </tr>
        </thead>
        <tbody id="rhtbody">
          {hist_table_html}
        </tbody>
      </table>
    </div>

  </div><!-- #mpanel-history -->

</div><!-- .wrap -->

<div class="footer">
  Summary Report &bull; {escape(gen_at)}
  &nbsp;&bull;&nbsp;
  <a href="patient_phase_report.html" target="_blank">Phase Breakdown Report</a>
</div>

<script>
{js_vars}
{_JS}
/* Second trend chart for history panel */
document.addEventListener('DOMContentLoaded', function() {{
  var el2 = document.getElementById('trendChartHist');
  if (el2 && window.Chart && _RUN_HISTORY.length > 0) {{
    var labels = _RUN_HISTORY.map(function(r) {{
      return r.session_num ? 'Session ' + r.session_num : (r.run_id || '').replace('run_','').replace(/_/g,' ');
    }});
    var rates = _RUN_HISTORY.map(function(r) {{ return r.summary ? r.summary.pass_rate : 0; }});
    var colors = rates.map(function(v) {{
      return v >= 90 ? '#52c41a' : (v >= 70 ? '#fa8c16' : '#ff4d4f');
    }});
    new Chart(el2.getContext('2d'), {{
      type: 'bar',
      data: {{
        labels: labels,
        datasets: [{{ label: 'Pass Rate %', data: rates,
          backgroundColor: colors, borderRadius: 4, borderSkipped: false }}]
      }},
      options: {{
        scales: {{
          y: {{ min: 0, max: 100, ticks: {{ callback: function(v) {{ return v + '%'; }} }} }},
          x: {{ ticks: {{ font: {{ size: 10 }} }} }}
        }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{ callbacks: {{
            title: function(items) {{
              var r = _RUN_HISTORY[items[0].dataIndex];
              var tests = (r.tests_executed || []).join(', ') || '(none)';
              return (r.session_num ? 'Session ' + r.session_num : items[0].label) + ' \u2014 ' + tests;
            }},
            label: function(c) {{ return c.raw + '%'; }}
          }} }}
        }}
      }}
    }});
  }}
}});
/* Fix duplicate tab IDs by wiring header nav buttons manually */
document.querySelectorAll('.hdr-nav .hnav-btn').forEach(function(btn) {{
  btn.addEventListener('click', function() {{
    document.querySelectorAll('.hdr-nav .hnav-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
  }});
}});
</script>
</body>
</html>"""

    @staticmethod
    def _row(r: TestResult) -> str:
        cls_map = {"PASS": "row-pass", "FAIL": "row-fail",
                   "ERROR": "row-error", "SKIP": "row-skip"}
        row_cls = cls_map.get(r.status, "")
        b_map   = {"PASS": "b-pass", "FAIL": "b-fail",
                   "ERROR": "b-error", "SKIP": "b-skip"}
        b_cls   = b_map.get(r.status, "b-skip")
        badge   = (
            f'<span class="badge {b_cls}" data-status="{escape(r.status)}">'
            f'{escape(r.status)}</span>'
        )
        if r.error:
            short  = escape(r.error[:90])
            suffix = "..." if len(r.error) > 90 else ""
            full   = escape(r.error)
            err_td = (
                f'<div class="err-cell">'
                f'<span class="err-short" onclick="toggleErr(this)"'
                f' title="Click to expand">{short}{suffix}</span>'
                f'<span class="err-full">{full}</span>'
                f'</div>'
            )
        else:
            err_td = "<span style=\"color:#8c8c8c\">&mdash;</span>"
        if r.screenshot_path:
            rel  = Path(r.screenshot_path).as_posix()
            shot = f'<a class="shot-link" href="../{rel}" target="_blank">View</a>'
        else:
            shot = "<span style=\"color:#8c8c8c\">&mdash;</span>"
        display_name = escape(patient_label(r.patient_id))
        pid_raw      = escape(str(r.patient_id))
        return (
            f'<tr class="{row_cls}">'
            f'<td class="test-cell">{escape(r.test_name)}</td>'
            f'<td class="mod-cell">{escape(r.module)}</td>'
            f'<td class="pid-cell" data-pid="{pid_raw}" title="{pid_raw}">{display_name}</td>'
            f'<td>{badge}</td>'
            f'<td>{err_td}</td>'
            f'<td>{shot}</td>'
            f'<td class="dur-cell">{r.duration}s</td>'
            f'</tr>'
        )

    def _run_hist_cards(self, runs: List[dict]) -> str:
        """Render 4 summary cards for run history."""
        total_runs = len(runs)
        if total_runs == 0:
            return (
                '<div class="hist-cards">'
                '<div class="hcard hc-total">'
                '<div class="hnum">0</div>'
                '<div class="hlbl">Total Runs</div>'
                '<div class="hsub">No history yet</div>'
                '</div>'
                '</div>'
            )
        rates = [r.get("summary", {}).get("pass_rate", 0) for r in runs]
        best  = max(rates)
        avg   = round(sum(rates) / len(rates), 1)
        last  = runs[-1]
        last_rate = last.get("summary", {}).get("pass_rate", 0)
        last_status = "PASS" if last_rate >= 90 else ("PARTIAL" if last_rate >= 70 else "FAIL")
        last_color  = "#389e0d" if last_rate >= 90 else ("#d46b08" if last_rate >= 70 else "#cf1322")
        last_rid = escape(last.get("run_id", ""))
        return f"""
<div class="hist-cards">
  <div class="hcard hc-total">
    <div class="hnum" style="color:#1677ff">{total_runs}</div>
    <div class="hlbl">Total Runs</div>
    <div class="hsub">All recorded runs</div>
  </div>
  <div class="hcard hc-best">
    <div class="hnum" style="color:#389e0d">{best}%</div>
    <div class="hlbl">Best Pass Rate</div>
    <div class="hsub">Peak performance</div>
  </div>
  <div class="hcard hc-last">
    <div class="hnum" style="color:{last_color}">{last_rate}%</div>
    <div class="hlbl">Last Run</div>
    <div class="hsub">{last_rid}</div>
  </div>
  <div class="hcard hc-avg">
    <div class="hnum" style="color:#08979c">{avg}%</div>
    <div class="hlbl">Avg Pass Rate</div>
    <div class="hsub">Across all runs</div>
  </div>
</div>"""

    def _run_hist_table(self, runs: List[dict], current_run_id: str) -> str:
        """Render the run history table rows with expandable detail rows."""
        if not runs:
            return (
                '<tr class="run-row">'
                '<td colspan="9" class="no-data">No run history found.</td>'
                '</tr>'
            )
        rows = []
        for idx, run in enumerate(runs):
            s      = run.get("summary", {})
            rid    = run.get("run_id", "")
            snum   = run.get("session_num", 0)
            date   = s.get("generated_at", "")[:10]
            ttl    = s.get("total", 0)
            psd    = s.get("passed", 0)
            fld    = s.get("failed", 0) + s.get("errors", 0)
            rate   = s.get("pass_rate", 0)
            dur    = s.get("duration_seconds", 0)
            is_cur = " (current)" if rid == current_run_id else ""
            sess_badge = (
                f'<span style="background:#e6f0ff;color:#1677ff;border-radius:8px;'
                f'padding:1px 8px;font-size:.72rem;font-weight:700;margin-left:6px">'
                f'Session {snum}</span>' if snum else ""
            )
            rate_color = "#389e0d" if rate >= 90 else ("#d46b08" if rate >= 70 else "#cf1322")
            rows.append(
                f'<tr class="run-row" data-session="{snum}">'
                f'<td>{idx + 1}</td>'
                f'<td class="run-id-cell">{escape(rid)}{escape(is_cur)}{sess_badge}</td>'
                f'<td>{escape(date)}</td>'
                f'<td>{ttl}</td>'
                f'<td style="color:#389e0d;font-weight:600">{psd}</td>'
                f'<td style="color:#cf1322;font-weight:600">{fld}</td>'
                f'<td style="color:{rate_color};font-weight:700">{rate}%</td>'
                f'<td>{dur}s</td>'
                f'<td><button class="open-btn" onclick="toggleRun(this, {idx})">Open</button></td>'
                f'</tr>'
                f'{self._run_detail_sub_table(run, idx)}'
            )
        return "\n".join(rows)

    def _run_detail_sub_table(self, run_data: dict, idx: int) -> str:
        """Render expandable detail sub-table for a historical run."""
        results = run_data.get("results", [])
        if not results:
            inner = '<p style="color:#8c8c8c;font-size:.82rem">No result details stored.</p>'
        else:
            trows = []
            for r in results:
                st     = r.get("status", "")
                b_map  = {"PASS": "b-pass", "FAIL": "b-fail", "ERROR": "b-error", "SKIP": "b-skip"}
                b_cls  = b_map.get(st, "b-skip")
                badge  = f'<span class="badge {b_cls}">{escape(st)}</span>'
                pid    = str(r.get("patient_id", ""))
                disp   = escape(patient_label(pid))
                trows.append(
                    f'<tr>'
                    f'<td>{escape(r.get("test_name",""))}</td>'
                    f'<td>{escape(r.get("module",""))}</td>'
                    f'<td title="{escape(pid)}">{disp}</td>'
                    f'<td>{badge}</td>'
                    f'<td>{r.get("duration",0)}s</td>'
                    f'</tr>'
                )
            inner = f"""
<table>
  <thead>
    <tr>
      <th>Test</th><th>Module</th><th>Patient</th><th>Status</th><th>Time</th>
    </tr>
  </thead>
  <tbody>{"".join(trows)}</tbody>
</table>"""
        return (
            f'<tr class="run-detail-row" id="rdr-{idx}">'
            f'<td colspan="9">'
            f'<div class="run-detail-inner">{inner}</div>'
            f'</td>'
            f'</tr>'
        )


# =============================================================================
# JSON REPORT GENERATOR
# =============================================================================
class JsonReportGenerator:
    def generate(self, results: List[TestResult], summary: dict, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "results": [asdict(r) for r in results]}
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# =============================================================================
# CSV REPORT GENERATOR
# =============================================================================
class CsvReportGenerator:
    _HEADERS = [
        "Test Name", "Module", "Patient ID", "Status",
        "Error", "Screenshot", "Duration (s)", "Timestamp",
    ]

    def generate(self, results: List[TestResult], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        buf = StringIO()
        writer = _csv.writer(buf, quoting=_csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(self._HEADERS)
        for r in results:
            writer.writerow([
                r.test_name, r.module, r.patient_id, r.status,
                r.error, r.screenshot_path, r.duration, r.timestamp,
            ])
        output_path.write_text(buf.getvalue(), encoding="utf-8-sig")


# =============================================================================
# PATIENT PHASE REPORT PATHS
# =============================================================================
PATIENT_PHASE_HTML = REPORTS_ROOT / "patient_phase_report.html"
PATIENT_PHASE_JSON = REPORTS_ROOT / "patient_phase_report.json"


# =============================================================================
# PATIENT PHASE HTML REPORT GENERATOR  (patient_phase_report.html)
# =============================================================================

# ---- Human-readable flow labels --------------------------------------------
_FLOW_LABELS: Dict[str, str] = {
    "test_e2e_acceptance":             "E2E Acceptance Flow",
    "test_e2e_b1_accession_rejection": "E2E B1 \u2014 Accession Rejection",
    "test_e2e_b2_labtech_rejection":   "E2E B2 \u2014 Lab Tech Rejection",
    "test_e2e_b3_doctor_resample":     "E2E B3 \u2014 Doctor Resample",
    "test_e2e_bc_combined_rejection":  "E2E BC \u2014 Combined Rejection",
}

# Ordered pipeline phases per flow (display order for pipeline stepper)
_FLOW_PHASE_ORDER: Dict[str, List[str]] = {
    "test_e2e_acceptance": [
        "Front Desk", "Phlebotomist", "Accession",
        "Lab Technician", "Doctor", "Published Reports",
    ],
    "test_e2e_b1_accession_rejection": [
        "Front Desk", "Phlebotomist",
        "Accession (Reject)", "Phlebotomist (Recollect)",
        "Accession (Re-accept)", "Lab Technician", "Doctor", "Published Reports",
    ],
    "test_e2e_b2_labtech_rejection": [
        "Front Desk", "Phlebotomist", "Accession",
        "Lab Technician (Reject)", "Accession (Reassign)",
        "Phlebotomist (Recollect)", "Accession (Re-accept)",
        "Lab Technician", "Doctor", "Published Reports",
    ],
    "test_e2e_b3_doctor_resample": [
        "Front Desk", "Phlebotomist", "Accession", "Lab Technician",
        "Doctor (Resample)", "Accession (Reassign)",
        "Phlebotomist (Recollect)", "Accession (Re-accept)",
        "Lab Technician (Re-save)", "Doctor (Approve)", "Published Reports",
    ],
    "test_e2e_bc_combined_rejection": [
        "Front Desk", "Phlebotomist",
        "Accession (Reject Serum)", "Phlebotomist (Recollect Serum)",
        "Accession (Re-accept Serum)", "Lab Technician (Reject 24h)",
        "Accession (Reassign 24h)", "Phlebotomist (Recollect 24h)",
        "Accession (Re-accept 24h)", "Lab Technician (Save All)",
        "Doctor (Resample LFT)", "Accession (Reassign Serum 2)",
        "Phlebotomist (Recollect Serum 2)", "Accession (Re-accept Serum 2)",
        "Lab Technician (Save LFT)", "Doctor (Approve All)", "Published Reports",
    ],
}

# ---- CSS -------------------------------------------------------------------
_PHASE_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --navy:#0d2137;--blue:#1677ff;--green:#52c41a;--dkgreen:#389e0d;
  --red:#ff4d4f;--dkred:#cf1322;--orange:#fa8c16;--dkorange:#d46b08;
  --purple:#722ed1;--teal:#08979c;
  --grey:#8c8c8c;--ltgrey:#bfbfbf;--bg:#f0f2f5;--surface:#fff;
  --border:#e8e8e8;--text:#1a1a1a;--text2:#595959;--text3:#8c8c8c;
  --r:8px;--sh:0 1px 6px rgba(0,0,0,.09);--sh2:0 4px 16px rgba(0,0,0,.14);
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,
     'Helvetica Neue',Arial,sans-serif;background:var(--bg);
     color:var(--text);font-size:14px;line-height:1.6;padding-bottom:56px}

/* ===== HEADER ===== */
.hdr{background:var(--navy);color:#fff;padding:14px 32px;
     display:flex;align-items:center;justify-content:space-between;
     position:sticky;top:0;z-index:300;box-shadow:0 2px 10px rgba(0,0,0,.4)}
.hdr-left h1{font-size:1.05rem;font-weight:700;letter-spacing:.02em}
.hdr-left .sub{font-size:.77rem;color:rgba(255,255,255,.52);margin-top:2px}
.hdr-right{display:flex;gap:24px}
.hdr-stat{text-align:center}
.hdr-stat .hs-num{font-size:1.5rem;font-weight:800;line-height:1}
.hdr-stat .hs-lbl{font-size:.68rem;color:rgba(255,255,255,.5);
                   text-transform:uppercase;letter-spacing:.08em}
.hs-green{color:#73d13d}.hs-red{color:#ff7875}.hs-orange{color:#ffd666}
.hs-grey{color:rgba(255,255,255,.4)}

/* ===== WRAP ===== */
.wrap{max-width:1500px;margin:0 auto;padding:24px 32px}

/* ===== PATIENT TABS ===== */
.ptab-wrap{display:flex;gap:0;border-bottom:2px solid var(--border);
           margin-bottom:20px;overflow-x:auto;white-space:nowrap}
.ptab{display:inline-flex;align-items:center;gap:6px;
      padding:9px 20px;border:none;background:transparent;
      cursor:pointer;font-size:.83rem;color:var(--text2);
      border-bottom:3px solid transparent;margin-bottom:-2px;
      transition:all .15s;white-space:nowrap;font-family:inherit;font-weight:500}
.ptab:hover{color:var(--blue);background:#f0f5ff}
.ptab.active{color:var(--blue);border-bottom-color:var(--blue);font-weight:700}
.ptab-panel{display:none}
.ptab-panel.active{display:block}
.pat-info-card{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
               padding:14px 20px;margin-bottom:16px;
               border-left:4px solid var(--purple);display:flex;flex-direction:column;gap:3px}
.pic-name{font-size:1rem;font-weight:700;color:var(--navy)}
.pic-id{font-size:.8rem;color:var(--text3);font-family:'Consolas','Courier New',monospace}

/* ===== OVERVIEW ROW ===== */
.overview{display:grid;grid-template-columns:1fr 260px;gap:20px;margin-bottom:24px}
@media(max-width:860px){.overview{grid-template-columns:1fr}}

/* Stat cards */
.stat-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));
            gap:12px;margin-bottom:16px}
.scard{background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
       padding:14px 16px;display:flex;flex-direction:column;align-items:center;
       gap:2px;border-top:3px solid var(--border);
       transition:transform .15s,box-shadow .15s}
.scard:hover{transform:translateY(-2px);box-shadow:var(--sh2)}
.scard.sc-total{border-color:#1677ff}.scard.sc-pass{border-color:var(--green)}
.scard.sc-fail{border-color:var(--red)}.scard.sc-notexec{border-color:#d9d9d9}
.scard.sc-flows{border-color:var(--purple)}.scard.sc-partial{border-color:var(--orange)}
.scard .sn{font-size:1.8rem;font-weight:700;line-height:1.1}
.scard .sl{font-size:.7rem;color:var(--text3);text-transform:uppercase;letter-spacing:.08em}
.sn-blue{color:#1677ff}.sn-green{color:var(--dkgreen)}.sn-red{color:var(--dkred)}
.sn-grey{color:var(--grey)}.sn-purple{color:var(--purple)}.sn-orange{color:var(--dkorange)}

/* Flow bars */
.bars-card{background:var(--surface);border-radius:var(--r);
           box-shadow:var(--sh);padding:16px 20px}
.bars-title{font-size:.75rem;font-weight:700;text-transform:uppercase;
            letter-spacing:.08em;color:var(--text2);margin-bottom:12px}
.fbar-row{display:flex;align-items:center;gap:10px;margin-bottom:9px}
.fbar-row:last-child{margin-bottom:0}
.fbar-label{font-size:.76rem;color:var(--text2);flex-shrink:0;
            width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fbar-track{flex:1;height:8px;background:#f0f0f0;border-radius:4px;overflow:hidden}
.fbar-fill{height:100%;border-radius:4px;transition:width .6s ease}
.fb-green{background:linear-gradient(90deg,#52c41a,#95de64)}
.fb-orange{background:linear-gradient(90deg,#fa8c16,#ffd591)}
.fb-red{background:linear-gradient(90deg,#ff4d4f,#ff7875)}
.fbar-pct{font-size:.74rem;font-weight:700;color:var(--text2);
           white-space:nowrap;width:52px;text-align:right}

/* Donut chart (Chart.js canvas) */
.donut-card{background:var(--surface);border-radius:var(--r);
            box-shadow:var(--sh);padding:20px;
            display:flex;flex-direction:column;align-items:center;gap:14px}
.donut-title{font-size:.75rem;font-weight:700;text-transform:uppercase;
             letter-spacing:.08em;color:var(--text2);align-self:flex-start}
.donut-svg-wrap{position:relative;display:flex;align-items:center;
                justify-content:center}
.donut-legend{display:flex;flex-direction:column;gap:7px;width:100%}
.leg-row{display:flex;align-items:center;gap:8px;font-size:.78rem;color:var(--text2)}
.leg-dot{width:11px;height:11px;border-radius:50%;flex-shrink:0}
.ld-pass{background:var(--green)}.ld-fail{background:var(--red)}
.ld-notexec{background:#d9d9d9}
.leg-val{margin-left:auto;font-weight:600;color:var(--text)}

/* ===== FLOW TABS ===== */
.flow-tabs-wrap{margin-bottom:16px;border-bottom:2px solid #e4e4e4;
                overflow-x:auto;white-space:nowrap}
.flow-tabs{display:inline-flex;gap:0}
.ftab{display:inline-flex;align-items:center;gap:6px;
      padding:8px 18px;border:none;background:transparent;
      cursor:pointer;font-size:.82rem;color:var(--text2);
      border-bottom:3px solid transparent;margin-bottom:-2px;
      transition:all .15s;white-space:nowrap;font-family:inherit}
.ftab:hover{color:var(--blue);background:#f0f5ff}
.ftab.active{color:var(--blue);font-weight:600;border-bottom-color:var(--blue)}
.ftab .tc{display:inline-flex;align-items:center;justify-content:center;
           width:18px;height:18px;border-radius:9px;font-size:.65rem;
           font-weight:700;margin-left:4px}
.tc-pass{background:#f6ffed;color:var(--dkgreen)}
.tc-fail{background:#fff2f0;color:var(--dkred)}
.tc-partial{background:#fff7e6;color:var(--dkorange)}
.tc-all{background:#e6f0ff;color:var(--blue)}

/* ===== STATUS FILTER + SEARCH ===== */
.sfilter-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;
             margin-bottom:14px}
.sfbtn{padding:3px 13px;border:1px solid #d9d9d9;border-radius:14px;
       background:var(--surface);cursor:pointer;font-size:.78rem;
       color:var(--text2);transition:all .12s;font-family:inherit}
.sfbtn:hover{border-color:var(--blue);color:var(--blue)}
.sfbtn.active{background:var(--blue);border-color:var(--blue);color:#fff;font-weight:600}
.sfbtn.sf-pass.active{background:var(--green);border-color:var(--green)}
.sfbtn.sf-fail.active{background:var(--red);border-color:var(--red)}
.sfbtn.sf-notexec.active{background:#8c8c8c;border-color:#8c8c8c}
.sbar-search{margin-left:auto;padding:4px 13px;border:1px solid #d9d9d9;
             border-radius:14px;font-size:.8rem;outline:none;min-width:210px;
             transition:border-color .12s;font-family:inherit}
.sbar-search:focus{border-color:var(--blue)}

/* ===== FLOW CARD ===== */
.flow-card{background:var(--surface);border-radius:var(--r);
           box-shadow:var(--sh);margin-bottom:24px;overflow:hidden;
           border:1px solid var(--border)}
.flow-header{display:flex;align-items:flex-start;justify-content:space-between;
             padding:14px 20px 12px;border-bottom:1px solid #f0f0f0;background:#fafafa}
.fh-left{display:flex;flex-direction:column;gap:3px}
.flow-title{font-size:.95rem;font-weight:700;color:var(--navy)}
.flow-meta{font-size:.74rem;color:var(--text3)}
.fh-right{display:flex;flex-direction:column;align-items:flex-end;gap:5px}
.flow-badge{padding:3px 12px;border-radius:12px;font-size:.76rem;
            font-weight:700;white-space:nowrap}
.fb-all-pass{background:#f6ffed;color:#237804;border:1px solid #b7eb8f}
.fb-partial{background:#fff7e6;color:#ad4e00;border:1px solid #ffd591}
.fb-all-fail{background:#fff2f0;color:#a8071a;border:1px solid #ffa39e}
.fb-notexec{background:#fafafa;color:var(--grey);border:1px solid #d9d9d9}
.flow-phase-stat{font-size:.74rem;color:var(--text3)}
.flow-phase-stat strong{color:var(--text2)}

/* ===== PIPELINE STEPPER ===== */
.pipeline-wrap{padding:16px 20px;border-bottom:1px solid #f5f5f5;
               overflow-x:auto;-webkit-overflow-scrolling:touch}
.pipeline-label{font-size:.7rem;font-weight:700;text-transform:uppercase;
                letter-spacing:.08em;color:var(--text3);margin-bottom:10px}
.pipeline{display:flex;align-items:stretch;gap:0;min-width:max-content}
.pnode{display:flex;flex-direction:column;align-items:center;justify-content:center;
       gap:5px;padding:10px 14px;border-radius:8px;min-width:88px;
       text-align:center;border:2px solid transparent;cursor:default;
       transition:transform .12s,box-shadow .12s}
.pnode:hover{transform:translateY(-2px);box-shadow:var(--sh2)}
.pn-pass{background:#f6ffed;border-color:#95de64}
.pn-fail{background:#fff2f0;border-color:#ffa39e}
.pn-notexec{background:#fafafa;border-color:#e8e8e8}
.pn-icon{font-size:1.2rem;line-height:1;font-weight:700}
.pn-pass .pn-icon{color:var(--green)}
.pn-fail .pn-icon{color:var(--red)}
.pn-notexec .pn-icon{color:#d9d9d9}
.pn-name{font-size:.65rem;color:var(--text2);line-height:1.3;
         max-width:82px;word-wrap:break-word}
.p-arrow{display:flex;align-items:center;padding:0 6px;
         color:var(--ltgrey);font-size:1.1rem;flex-shrink:0;align-self:center}

/* ===== 4-COLUMN PHASE TABLE ===== */
.tbl-outer{overflow-x:auto}
.phase-tbl{width:100%;border-collapse:collapse}
.phase-tbl thead th{
  background:var(--navy);color:rgba(255,255,255,.85);
  padding:10px 16px;text-align:left;font-size:.7rem;
  text-transform:uppercase;letter-spacing:.07em;
  white-space:nowrap;cursor:pointer;user-select:none;position:sticky;top:48px}
.phase-tbl thead th:hover{background:#1a3550}
.phase-tbl thead th .si{margin-left:4px;opacity:.4;font-size:.68rem}
.phase-tbl thead th.sorted .si{opacity:1}
.phase-tbl tbody td{
  padding:9px 16px;border-bottom:1px solid #f5f5f5;
  font-size:.84rem;vertical-align:middle}
.phase-tbl tbody tr:last-child td{border-bottom:none}
.tr-pass{background:#fff}
.tr-pass:hover{background:#f6ffed}
.tr-fail{background:#fffafa}
.tr-fail:hover{background:#fff2f0}
.tr-notexec{background:#fafafa}
.tr-notexec:hover{background:#f5f5f5}
.td-pid{font-weight:700;color:var(--blue);white-space:nowrap;min-width:60px}
.td-flow{color:var(--text2);font-size:.81rem;max-width:220px}
.td-phase{color:#262626;font-weight:500}
.td-status{white-space:nowrap;min-width:120px}

/* Status badges in table */
.pbadge{display:inline-flex;align-items:center;gap:5px;
        padding:3px 10px;border-radius:10px;
        font-size:.76rem;font-weight:700;white-space:nowrap}
.pb-pass{background:#f6ffed;color:#237804;border:1px solid #b7eb8f}
.pb-fail{background:#fff2f0;color:#a8071a;border:1px solid #ffa39e}
.pb-notexec{background:#fafafa;color:var(--grey);border:1px solid #d9d9d9}

/* Error detail inside fail cell */
.err-detail{margin-top:5px;font-size:.74rem;color:var(--dkred);
            line-height:1.4;max-width:340px;white-space:normal;
            word-break:break-word}
.err-toggle{font-size:.72rem;color:var(--blue);cursor:pointer;
            text-decoration:underline dotted;display:inline-block;margin-top:2px}
.err-full-text{display:none;font-size:.72rem;color:var(--dkred);
               margin-top:3px;white-space:pre-wrap;word-break:break-word}
.err-expanded .err-full-text{display:block}
.err-expanded .err-toggle{display:none}
a.pshot{font-size:.73rem;color:var(--blue);text-decoration:none;
        display:inline-flex;align-items:center;gap:3px;margin-top:3px}
a.pshot:hover{text-decoration:underline}

/* No data */
.no-phase-data{text-align:center;padding:48px;color:var(--text3);font-size:.92rem}

/* Legend */
.legend-row{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px}
.leg-item{display:flex;align-items:center;gap:7px;font-size:.78rem;color:var(--text2)}
.leg-swatch{width:13px;height:13px;border-radius:3px;flex-shrink:0}
.ls-pass{background:#d9f7be;border:1px solid #95de64}
.ls-fail{background:#ffccc7;border:1px solid #ff7875}
.ls-notexec{background:#f0f0f0;border:1px solid #d9d9d9}

/* Footer */
.footer{margin-top:24px;text-align:center;font-size:.74rem;color:var(--text3)}
.footer a{color:var(--blue);text-decoration:none}
.footer a:hover{text-decoration:underline}

/* ===== SESSION META BAR ===== */
.session-meta-bar{
  background:var(--surface);border-radius:var(--r);box-shadow:var(--sh);
  padding:13px 20px;margin-bottom:16px;display:flex;align-items:flex-start;
  gap:28px;flex-wrap:wrap;border-left:4px solid var(--blue)
}
.sm-item{display:flex;flex-direction:column;gap:2px}
.sm-item.sm-wide{flex:1;min-width:220px}
.sm-lbl{font-size:.62rem;text-transform:uppercase;letter-spacing:.09em;color:var(--text3)}
.sm-val{font-size:.88rem;font-weight:600;color:var(--text)}
.sm-tests-val{font-size:.82rem;font-weight:400;color:var(--text2);line-height:1.5;white-space:normal}
/* Session tab count badge */
.stab-cnt{background:#e6f0ff;color:var(--blue);border-radius:10px;
          padding:1px 7px;font-size:.7rem;font-weight:700;margin-left:6px}
.ptab.active .stab-cnt{background:var(--blue);color:#fff}
/* global filter bar (above session tabs) */
.global-filter-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
"""

# ---- JavaScript ------------------------------------------------------------
_PHASE_JS = """
/* ---- Session tab switching ---- */
function showSessionTab(snum) {
  document.querySelectorAll('.ptab').forEach(function(t) { t.classList.remove('active'); });
  document.querySelectorAll('.ptab-panel').forEach(function(p) { p.classList.remove('active'); });
  var btn = document.getElementById('ptab-btn-s' + snum);
  var pnl = document.getElementById('ptab-panel-s' + snum);
  if (btn) btn.classList.add('active');
  if (pnl) pnl.classList.add('active');
  /* reset filters when switching sessions */
  _status = 'ALL'; _search = '';
  document.querySelectorAll('.sfbtn').forEach(function(b) { b.classList.remove('active'); });
  var allBtn = document.getElementById('psf-ALL');
  if (allBtn) allBtn.classList.add('active');
  var searchBox = document.querySelector('.sbar-search');
  if (searchBox) searchBox.value = '';
  applyPhaseFilters();
}

/* ---- Status filter (applies to active session panel only) ---- */
var _status = 'ALL', _search = '';
function filterStatus(s) {
  _status = s;
  document.querySelectorAll('.sfbtn').forEach(function(b) { b.classList.remove('active'); });
  var btn = document.getElementById('psf-' + s);
  if (btn) btn.classList.add('active');
  applyPhaseFilters();
}
function onSearch(q) { _search = q.toLowerCase(); applyPhaseFilters(); }

function applyPhaseFilters() {
  var activePanel = document.querySelector('.ptab-panel.active');
  var scope = activePanel ? activePanel : document;
  scope.querySelectorAll('.phase-tbl tbody tr').forEach(function(tr) {
    var ok = true;
    if (_status !== 'ALL') {
      var b = tr.querySelector('.pbadge');
      if (!b || b.getAttribute('data-ps') !== _status) ok = false;
    }
    if (ok && _search) ok = tr.textContent.toLowerCase().indexOf(_search) >= 0;
    tr.style.display = ok ? '' : 'none';
  });
}

/* ---- Sort phase table ---- */
function toggleErrFull(el) { el.closest('.td-status').classList.toggle('err-expanded'); }
var _sortIdx = {};
function sortPhaseCol(tblId, col) {
  var key = tblId + ':' + col;
  _sortIdx[key] = !_sortIdx[key];
  var asc = _sortIdx[key];
  var tbody = document.querySelector('#' + tblId + ' tbody');
  if (!tbody) return;
  var rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a, b) {
    var av = a.cells[col] ? a.cells[col].textContent.trim() : '';
    var bv = b.cells[col] ? b.cells[col].textContent.trim() : '';
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(function(r) { tbody.appendChild(r); });
  var ths = document.querySelectorAll('#' + tblId + ' thead th');
  ths.forEach(function(th, i) {
    var si = th.querySelector('.si');
    if (si) si.innerHTML = i === col ? (asc ? '&#9650;' : '&#9660;') : '&#8597;';
    th.classList.toggle('sorted', i === col);
  });
  applyPhaseFilters();
}

/* ---- Chart.js donut for batch totals in header ---- */
document.addEventListener('DOMContentLoaded', function() {
  var el = document.getElementById('phaseDonut');
  if (el && window.Chart) {
    new Chart(el.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['Passed', 'Failed', 'Not Executed'],
        datasets: [{
          data: [_PH_PASS, _PH_FAIL, _PH_NOTEXEC],
          backgroundColor: ['#52c41a', '#ff4d4f', '#d9d9d9'],
          borderWidth: 2, borderColor: '#fff'
        }]
      },
      options: {
        cutout: '68%',
        plugins: { legend: { position: 'bottom', labels: { padding: 10, font: { size: 11 } } } }
      }
    });
  }
});
"""


class _DictEntry:
    """
    Thin wrapper that lets plain dicts (from saved JSON snapshots) behave
    like PhaseEntry dataclass instances in existing renderer methods.
    """
    __slots__ = ("patient_id", "phase_name", "status", "error", "screenshot_path", "timestamp")

    def __init__(self, d: dict) -> None:
        self.patient_id      = d.get("patient_id",      "")
        self.phase_name      = d.get("phase_name",      "")
        self.status          = d.get("status",          "NOT EXECUTED")
        self.error           = d.get("error",           "")
        self.screenshot_path = d.get("screenshot_path", "")
        self.timestamp       = d.get("timestamp",       "")


class PatientPhaseHtmlGenerator:
    """
    Generates the patient-phase HTML report with Session-based tabs.

    Layout
    ------
    Header  : batch-wide phase stats (pass rate, counts)
    Filter  : shared status filter + search (above tabs)
    Tabs    : Session 1 | Session 2 | Session 3 ...  (latest = default active)
    Panel   : session meta bar + stat cards + flow bars + flow cards
              Each flow card → pipeline stepper + 4-column phase table
                               (Patient | Executed Flow | Section | Status)

    Rotation: after SESSIONS_PER_BATCH (10) sessions the caller writes to a
              new file (summary_report2.html / patient_phase_report2.html, etc.)
              so each file stays ≤ 10 sessions.
    """

    # ------------------------------------------------------------------ entry
    def generate(
        self,
        phase_tracker,
        output_path:         Path,
        current_session_num: int  = 1,
        batch:               int  = 1,
    ) -> None:
        """
        Generate the phase HTML report.

        Parameters
        ----------
        phase_tracker        : live PhaseTracker (used as fallback if no snapshots)
        output_path          : where to write the HTML file
        current_session_num  : session number just completed
        batch                : report-file batch number (1 → default names)
        """
        batch_sessions = load_batch_sessions(batch)

        # Fallback: if no batch sessions found (e.g. very first run before registry
        # was populated), synthesise a session dict from the live tracker.
        if not batch_sessions and phase_tracker.has_data():
            from dataclasses import asdict as _asdict
            raw_data = phase_tracker.get_report_data()
            phase_data: dict = {}
            for tn, patient_map in raw_data.items():
                phase_data[tn] = {
                    pid: [_asdict(e) for e in entries]
                    for pid, entries in patient_map.items()
                }
            batch_sessions = [{
                "session_num":      current_session_num,
                "run_id":           "",
                "start_time":       "",
                "end_time":         datetime.now().isoformat(timespec="seconds"),
                "duration_seconds": 0,
                "tests_executed":   list(phase_data.keys()),
                "summary":          {},
                "phase_data":       phase_data,
            }]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            self._build(batch_sessions, current_session_num),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ build
    def _build(
        self,
        batch_sessions:      List[dict],
        current_session_num: int,
    ) -> str:
        now = datetime.now().isoformat(timespec="seconds")

        if not batch_sessions:
            return self._empty_html(now)

        # --- Batch-wide totals (shown in header) --------------------------------
        b_total = b_pass = b_fail = b_notexec = 0
        for sess in batch_sessions:
            for _tn, patient_map in sess.get("phase_data", {}).items():
                for _pid, entries in patient_map.items():
                    for e in entries:
                        st = e.get("status", "NOT EXECUTED") if isinstance(e, dict) else e.status
                        b_total += 1
                        if st == "PASSED":   b_pass    += 1
                        elif st == "FAILED": b_fail    += 1
                        else:                b_notexec += 1

        batch_pass_rate = round(b_pass / b_total * 100, 1) if b_total else 0.0
        pr_cls = "hs-green" if batch_pass_rate >= 90 else (
            "hs-orange" if batch_pass_rate >= 60 else "hs-red"
        )

        # --- Determine which session tab is active by default ------------------
        snums_present = {s.get("session_num", 0) for s in batch_sessions}
        default_active = (
            current_session_num if current_session_num in snums_present
            else batch_sessions[-1].get("session_num", 1)
        )

        # --- Build session tab strip + panels ----------------------------------
        tabs_html   = ""
        panels_html = ""
        for sess in batch_sessions:
            snum      = sess.get("session_num", 1)
            is_active = (snum == default_active)
            n_flows   = len(sess.get("phase_data", {}))
            active_c  = "active" if is_active else ""
            tabs_html += (
                f'<button class="ptab {active_c}" id="ptab-btn-s{snum}"'
                f' onclick="showSessionTab({snum})">'
                f'Session {snum}'
                f'<span class="stab-cnt">{n_flows}</span>'
                f'</button>\n'
            )
            panels_html += self._session_panel(sess, snum, is_active)

        js_vars = (
            f"var _PH_PASS = {b_pass};\n"
            f"var _PH_FAIL = {b_fail};\n"
            f"var _PH_NOTEXEC = {b_notexec};\n"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Phase Breakdown Report &mdash; {escape(now[:10])}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>{_PHASE_CSS}</style>
</head>
<body>

<!-- ===== HEADER ===== -->
<header class="hdr">
  <div class="hdr-left">
    <h1>E2E Phase Breakdown Report</h1>
    <div class="sub">
      Session &bull; Flow &bull; Patient &bull; Phase &bull; Status
      &nbsp;&mdash;&nbsp; Generated: {escape(now)}
    </div>
  </div>
  <div class="hdr-right">
    <div class="hdr-stat">
      <div class="hs-num {pr_cls}">{batch_pass_rate}%</div>
      <div class="hs-lbl">Phase Pass</div>
    </div>
    <div class="hdr-stat">
      <div class="hs-num hs-green">{b_pass}</div>
      <div class="hs-lbl">Passed</div>
    </div>
    <div class="hdr-stat">
      <div class="hs-num hs-red">{b_fail}</div>
      <div class="hs-lbl">Failed</div>
    </div>
    <div class="hdr-stat">
      <div class="hs-num hs-grey">{b_notexec}</div>
      <div class="hs-lbl">Not Exec</div>
    </div>
    <div class="hdr-stat">
      <div class="hs-num" style="color:#ffd666">{len(batch_sessions)}</div>
      <div class="hs-lbl">Sessions</div>
    </div>
  </div>
</header>

<!-- ===== CONTENT ===== -->
<div class="wrap">

  <!-- Global status filter + search (above tabs, filters active session) -->
  <div class="global-filter-bar">
    <button id="psf-ALL"          class="sfbtn active"     onclick="filterStatus('ALL')">All</button>
    <button id="psf-PASSED"       class="sfbtn sf-pass"    onclick="filterStatus('PASSED')">&#10003; Passed</button>
    <button id="psf-FAILED"       class="sfbtn sf-fail"    onclick="filterStatus('FAILED')">&#10007; Failed</button>
    <button id="psf-NOT EXECUTED" class="sfbtn sf-notexec" onclick="filterStatus('NOT EXECUTED')">&#9711; Not Executed</button>
    <input class="sbar-search" type="text"
           placeholder="Search patient, section, flow..."
           oninput="onSearch(this.value)">
  </div>

  <!-- Session tabs -->
  <div class="ptab-wrap">
    {tabs_html}
  </div>

  <!-- Session panels -->
  {panels_html}

</div><!-- .wrap -->

<div class="footer">
  Phase Breakdown Report &bull; {escape(now)}
  &nbsp;&bull;&nbsp;
  <a href="summary_report.html">&#8592; Back to Summary Report</a>
</div>

<script>
{js_vars}
{_PHASE_JS}
</script>
</body>
</html>"""

    # ---------------------------------------------------------------- session panel

    def _session_panel(self, sess: dict, snum: int, is_active: bool) -> str:
        """Render the full content panel for one session tab."""
        phase_data     = sess.get("phase_data", {})
        summary        = sess.get("summary", {})
        start_time     = sess.get("start_time", "")
        end_time       = sess.get("end_time", summary.get("generated_at", ""))
        duration       = sess.get("duration_seconds", summary.get("duration_seconds", 0))
        tests_executed = sess.get("tests_executed", list(phase_data.keys()))

        # --- Session-level phase stats ---
        s_total = s_pass = s_fail = s_notexec = 0
        flow_stats: List[dict] = []
        for tn, patient_map in phase_data.items():
            f_total = f_pass = f_fail = 0
            for _pid, entries in patient_map.items():
                for e in entries:
                    st = e.get("status", "NOT EXECUTED") if isinstance(e, dict) else e.status
                    s_total  += 1
                    f_total  += 1
                    if st == "PASSED":   s_pass  += 1; f_pass  += 1
                    elif st == "FAILED": s_fail  += 1; f_fail  += 1
                    else:                s_notexec += 1
            flow_stats.append({
                "test_name": tn,
                "label":     self._flow_label(tn),
                "total":     f_total,
                "passed":    f_pass,
                "failed":    f_fail,
            })

        # --- Meta bar values ---
        date_str  = (start_time or end_time)[:10]
        start_str = start_time[11:19] if len(start_time) > 10 else ""
        end_str   = end_time[11:19]   if len(end_time)   > 10 else ""
        tests_str = ", ".join(
            self._flow_label(t) for t in tests_executed
        ) or "\u2014"

        start_item = (
            f'<div class="sm-item">'
            f'<div class="sm-lbl">Start</div>'
            f'<div class="sm-val">{escape(start_str)}</div>'
            f'</div>' if start_str else ""
        )
        end_item = (
            f'<div class="sm-item">'
            f'<div class="sm-lbl">End</div>'
            f'<div class="sm-val">{escape(end_str)}</div>'
            f'</div>' if end_str else ""
        )

        meta_bar = f"""
<div class="session-meta-bar">
  <div class="sm-item">
    <div class="sm-lbl">Session</div>
    <div class="sm-val">#{snum}</div>
  </div>
  <div class="sm-item">
    <div class="sm-lbl">Date</div>
    <div class="sm-val">{escape(date_str)}</div>
  </div>
  {start_item}
  {end_item}
  <div class="sm-item">
    <div class="sm-lbl">Duration</div>
    <div class="sm-val">{duration}s</div>
  </div>
  <div class="sm-item sm-wide">
    <div class="sm-lbl">Tests Executed</div>
    <div class="sm-val sm-tests-val">{escape(tests_str)}</div>
  </div>
</div>"""

        # --- Stat cards ---
        stat_cards = f"""
<div class="stat-cards">
  <div class="scard sc-total">
    <div class="sn sn-blue">{s_total}</div>
    <div class="sl">Total Phases</div>
  </div>
  <div class="scard sc-pass">
    <div class="sn sn-green">{s_pass}</div>
    <div class="sl">Passed</div>
  </div>
  <div class="scard sc-fail">
    <div class="sn sn-red">{s_fail}</div>
    <div class="sl">Failed</div>
  </div>
  <div class="scard sc-notexec">
    <div class="sn sn-grey">{s_notexec}</div>
    <div class="sl">Not Executed</div>
  </div>
  <div class="scard sc-flows">
    <div class="sn sn-purple">{len(flow_stats)}</div>
    <div class="sl">Flows</div>
  </div>
</div>"""

        bars_html = self._flow_bars(flow_stats)

        # --- Legend ---
        legend = """
<div class="legend-row" style="margin-top:12px;margin-bottom:14px">
  <div class="leg-item"><div class="leg-swatch ls-pass"></div> <span>Phase Passed</span></div>
  <div class="leg-item"><div class="leg-swatch ls-fail"></div>
    <span>Phase Failed &mdash; subsequent sections not executed</span></div>
  <div class="leg-item"><div class="leg-swatch ls-notexec"></div>
    <span>Not Executed &mdash; skipped due to earlier failure</span></div>
</div>"""

        # --- Flow cards ---
        flow_cards_html = ""
        for tn, patient_map in phase_data.items():
            phases   = _FLOW_PHASE_ORDER.get(tn) or self._phases_from_data(patient_map)
            patients = list(patient_map.keys())
            # Wrap dict entries so existing _flow_card / _phase_table work unchanged
            wrapped: Dict[str, list] = {
                pid: [_DictEntry(e) if isinstance(e, dict) else e for e in entries]
                for pid, entries in patient_map.items()
            }
            flow_cards_html += self._flow_card(tn, phases, patients, wrapped)

        if not flow_cards_html:
            flow_cards_html = (
                '<div class="no-phase-data">No phase data recorded in this session.</div>'
            )

        active_cls = "active" if is_active else ""
        return f"""
<div id="ptab-panel-s{snum}" class="ptab-panel {active_cls}">
  {meta_bar}
  <div class="overview">
    <div>
      {stat_cards}
      <div class="bars-card">
        <div class="bars-title">Flow Completion Rate</div>
        {bars_html}
      </div>
    </div>
    <!-- Donut chart for this session -->
    <div class="donut-card">
      <div class="donut-title">Phase Distribution</div>
      <div class="donut-svg-wrap">
        {self._svg_donut(s_pass, s_fail, s_notexec, s_total)}
      </div>
      <div class="donut-legend">
        <div class="leg-row">
          <div class="leg-dot ld-pass"></div><span>Passed</span>
          <span class="leg-val">{s_pass}</span>
        </div>
        <div class="leg-row">
          <div class="leg-dot ld-fail"></div><span>Failed</span>
          <span class="leg-val">{s_fail}</span>
        </div>
        <div class="leg-row">
          <div class="leg-dot ld-notexec"></div><span>Not Executed</span>
          <span class="leg-val">{s_notexec}</span>
        </div>
      </div>
    </div>
  </div>
  {legend}
  {flow_cards_html}
</div>"""

    @staticmethod
    def _phases_from_data(patient_map: dict) -> List[str]:
        """Derive phase order from the data when _FLOW_PHASE_ORDER has no entry."""
        seen: Dict[str, int] = {}
        for entries in patient_map.values():
            for i, e in enumerate(entries):
                ph = (e.get("phase_name") if isinstance(e, dict) else e.phase_name) or ""
                if ph and ph not in seen:
                    seen[ph] = i
        return sorted(seen, key=lambda p: seen[p])

    @staticmethod
    def _empty_html(now: str) -> str:
        return (
            f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
            f'<title>Phase Report</title></head><body>'
            f'<p style="padding:40px;font-family:sans-serif;color:#8c8c8c">'
            f'No phase data recorded yet. Generated: {escape(now)}</p>'
            f'</body></html>'
        )

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _flow_label(test_name: str) -> str:
        return _FLOW_LABELS.get(
            test_name,
            test_name.replace("_", " ").title(),
        )

    def _patient_tab_strip(self, pids: List[str]) -> str:
        """Render patient tab buttons (excluding overall which is rendered inline)."""
        tabs = []
        for pid in pids:
            display = escape(patient_label(pid))
            pid_e   = escape(pid)
            tabs.append(
                f'<button class="ptab" id="ptab-btn-{pid_e}"'
                f' onclick="showPatientTab(\'{pid_e}\')">'
                f'{display}</button>'
            )
        return "\n".join(tabs)

    def _patient_tab_panel(
        self,
        pid: str,
        data: dict,
        all_test_names: List[str],
        phase_tracker,
    ) -> str:
        """Render the content panel for a single patient tab."""
        display = patient_label(pid)
        sections = []
        for test_name in all_test_names:
            patient_map = data.get(test_name, {})
            if pid not in patient_map:
                continue
            entries = patient_map[pid]
            phases  = phase_tracker.phases_for_test(test_name)
            label   = self._flow_label(test_name)

            # Build patient-specific pipeline
            agg     = {e.phase_name: e.status for e in entries}
            pipeline = self._pipeline_html(phases, agg)

            # Flow status badge
            f_pass = sum(1 for e in entries if e.status == "PASSED")
            f_fail = sum(1 for e in entries if e.status == "FAILED")
            if f_fail == 0 and f_pass > 0:
                badge_cls, badge_txt = "fb-all-pass", "All Phases Passed"
            elif f_fail > 0 and f_pass > 0:
                badge_cls, badge_txt = "fb-partial", "Partially Passed"
            elif f_fail > 0:
                badge_cls, badge_txt = "fb-all-fail", "Flow Failed"
            else:
                badge_cls, badge_txt = "fb-notexec", "Not Executed"

            tbl_id   = re.sub(r"[^\w]", "_", f"{test_name}_{pid}")
            tbl_rows = self._patient_phase_rows(label, phases, entries)
            sections.append(f"""
<div class="flow-card" style="margin-bottom:16px" data-flow="{escape(test_name)}">
  <div class="flow-header">
    <div class="fh-left">
      <div class="flow-title">{escape(label)}</div>
      <div class="flow-meta">{len(phases)} phases</div>
    </div>
    <div class="fh-right">
      <span class="flow-badge {badge_cls}">{badge_txt}</span>
    </div>
  </div>
  <div class="pipeline-wrap">
    <div class="pipeline-label">Execution Pipeline</div>
    {pipeline}
  </div>
  <div class="tbl-outer">
    <table class="phase-tbl" id="{tbl_id}">
      <thead>
        <tr>
          <th onclick="sortPhaseCol('{tbl_id}',0)">Flow<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',1)">Section<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',2)">Status<span class="si">&#8597;</span></th>
        </tr>
      </thead>
      <tbody>{tbl_rows}</tbody>
    </table>
  </div>
</div>""")

        content = "\n".join(sections) if sections else (
            '<div class="no-phase-data">No phase data for this patient.</div>'
        )
        pid_e   = escape(pid)
        disp_e  = escape(display)
        return f"""
<div id="ptab-panel-{pid_e}" class="ptab-panel">
  <div class="pat-info-card">
    <div class="pic-name">{disp_e}</div>
    <div class="pic-id">Patient ID: {pid_e}</div>
  </div>
  {content}
</div>"""

    def _patient_phase_rows(
        self,
        flow_label: str,
        phases: List[str],
        entries: list,
    ) -> str:
        """Render phase table rows for a single patient (3-column: Flow | Section | Status)."""
        entry_map = {e.phase_name: e for e in entries}
        rows = []
        for phase in phases:
            entry = entry_map.get(phase)
            if entry is None or entry.status == "NOT EXECUTED":
                row_cls      = "tr-notexec"
                status_inner = (
                    f'<span class="pbadge pb-notexec" data-ps="NOT EXECUTED">'
                    f'&#9711; Not Executed</span>'
                )
            elif entry.status == "PASSED":
                row_cls  = "tr-pass"
                shot_link = ""
                if entry.screenshot_path:
                    rel = Path(entry.screenshot_path).as_posix()
                    shot_link = (
                        f' <a class="pshot" href="../{rel}" target="_blank">&#128247;</a>'
                    )
                status_inner = (
                    f'<span class="pbadge pb-pass" data-ps="PASSED">&#10003; Passed</span>'
                    f'{shot_link}'
                )
            else:  # FAILED
                row_cls   = "tr-fail"
                err_short = escape(entry.error[:100]) + ("..." if len(entry.error) > 100 else "")
                err_html  = (
                    f'<div class="err-detail">{err_short}</div>'
                    if entry.error else ""
                )
                shot_html = ""
                if entry.screenshot_path:
                    rel = Path(entry.screenshot_path).as_posix()
                    shot_html = (
                        f'<a class="pshot" href="../{rel}" target="_blank">'
                        f'&#128247; Screenshot</a>'
                    )
                status_inner = (
                    f'<span class="pbadge pb-fail" data-ps="FAILED">&#10007; Failed</span>'
                    f'{err_html}{shot_html}'
                )
            rows.append(
                f'<tr class="{row_cls}">'
                f'<td class="td-flow">{escape(flow_label)}</td>'
                f'<td class="td-phase">{escape(phase)}</td>'
                f'<td class="td-status">{status_inner}</td>'
                f'</tr>'
            )
        return "\n".join(rows)

    # ---------------------------------------------------------------- svg donut (kept for flow bars)
    def _svg_donut(
        self,
        passed: int,
        failed: int,
        not_exec: int,
        total: int,
    ) -> str:
        if total == 0:
            return (
                '<svg viewBox="0 0 200 200" width="180" height="180">'
                '<circle cx="100" cy="100" r="70" fill="none" stroke="#f0f0f0" stroke-width="28"/>'
                '<text x="100" y="100" text-anchor="middle" dominant-baseline="middle" '
                'font-size="13" fill="#8c8c8c">No data</text>'
                '</svg>'
            )

        C = 2 * math.pi * 70  # circumference using midpoint radius

        def seg(color: str, length: float, offset: float) -> str:
            if length <= 0:
                return ""
            return (
                f'<circle cx="100" cy="100" r="70" fill="none" '
                f'stroke="{color}" stroke-width="28" '
                f'stroke-linecap="butt" '
                f'stroke-dasharray="{length:.3f} {C:.3f}" '
                f'stroke-dashoffset="{-offset:.3f}" '
                f'transform="rotate(-90 100 100)"/>'
            )

        p_len = (passed   / total) * C
        f_len = (failed   / total) * C
        n_len = (not_exec / total) * C

        pct = round(passed / total * 100, 1)
        pct_color = "#52c41a" if pct >= 90 else ("#fa8c16" if pct >= 60 else "#ff4d4f")

        segments = ""
        acc = 0.0
        if p_len > 0:
            segments += seg("#52c41a", p_len, acc)
            acc += p_len
        if f_len > 0:
            segments += seg("#ff4d4f", f_len, acc)
            acc += f_len
        if n_len > 0:
            segments += seg("#d9d9d9", n_len, acc)

        return (
            f'<svg viewBox="0 0 200 200" width="180" height="180">'
            f'<circle cx="100" cy="100" r="70" fill="none" stroke="#f5f5f5" stroke-width="28"/>'
            f'{segments}'
            f'<text x="100" y="92" text-anchor="middle" font-size="24" '
            f'font-weight="800" fill="{pct_color}">{pct}%</text>'
            f'<text x="100" y="114" text-anchor="middle" font-size="10" fill="#8c8c8c">Phase Pass Rate</text>'
            f'</svg>'
        )

    # ---------------------------------------------------------------- flow bars
    def _flow_bars(self, flow_stats: List[dict]) -> str:
        if not flow_stats:
            return "<p style=\"color:#8c8c8c;font-size:.82rem\">No flow data.</p>"
        rows = []
        for fs in flow_stats:
            pct     = round(fs["passed"] / fs["total"] * 100, 1) if fs["total"] else 0.0
            bar_cls = "fb-green" if pct == 100 else ("fb-orange" if pct > 50 else "fb-red")
            rows.append(
                f'<div class="fbar-row">'
                f'<div class="fbar-label" title="{escape(fs["label"])}">'
                f'{escape(fs["label"])}</div>'
                f'<div class="fbar-track">'
                f'<div class="fbar-fill {bar_cls}" style="width:{pct}%"></div>'
                f'</div>'
                f'<div class="fbar-pct">{fs["passed"]}/{fs["total"]}</div>'
                f'</div>'
            )
        return "\n".join(rows)

    # ---------------------------------------------------------------- tabs
    def _tabs(self, flow_stats: List[dict]) -> str:
        def _tab_count_cls(fs: dict) -> str:
            if fs["failed"] == 0:
                return "tc-pass"
            if fs["failed"] > 0 and fs["passed"] > 0:
                return "tc-partial"
            return "tc-fail"

        tabs = [
            f'<button class="ftab active" data-flow="ALL" onclick="showFlow(\'ALL\')">'
            f'All Flows<span class="tc tc-all">{len(flow_stats)}</span></button>'
        ]
        for fs in flow_stats:
            tc_cls = _tab_count_cls(fs)
            label  = escape(fs["label"])
            tn     = escape(fs["test_name"])
            short  = label.replace("E2E ", "").replace(" Flow", "")
            tabs.append(
                f'<button class="ftab" data-flow="{tn}" '
                f'onclick="showFlow(\'{tn}\')">'
                f'{short}<span class="tc {tc_cls}">'
                f'{fs["passed"]}/{fs["total"]}</span></button>'
            )

        return (
            f'<div class="flow-tabs-wrap">'
            f'<div class="flow-tabs">{"".join(tabs)}</div>'
            f'</div>'
        )

    # ---------------------------------------------------------------- flow card
    def _flow_card(
        self,
        test_name:   str,
        phases:      List[str],
        patients:    List[str],
        patient_map: dict,
    ) -> str:
        label = self._flow_label(test_name)

        # Compute flow-level pass/fail counts
        f_pass = f_fail = f_notexec = 0
        for pid in patients:
            for e in patient_map.get(pid, []):
                if e.status == "PASSED":
                    f_pass += 1
                elif e.status == "FAILED":
                    f_fail += 1
                else:
                    f_notexec += 1
        f_total = f_pass + f_fail + f_notexec

        # Flow badge
        if f_fail == 0 and f_pass > 0:
            badge_cls, badge_txt = "fb-all-pass", "&#10003; All Phases Passed"
        elif f_fail > 0 and f_pass > 0:
            badge_cls, badge_txt = "fb-partial", "&#9888; Partially Passed"
        elif f_fail > 0 and f_pass == 0:
            badge_cls, badge_txt = "fb-all-fail", "&#10007; Flow Failed"
        else:
            badge_cls, badge_txt = "fb-notexec", "&#9711; Not Executed"

        meta = f"{len(patients)} patient(s) &bull; {f_total} phase executions"
        stat = (
            f'<strong>{f_pass}</strong>/{f_total} phases passed'
            f'{f", &nbsp;<strong style=\"color:#cf1322\">" + str(f_fail) + "</strong> failed" if f_fail else ""}'
        )

        # Phase statuses aggregated across all patients (worst wins)
        agg_statuses = self._aggregate_pipeline(phases, patients, patient_map)

        # Pipeline stepper
        pipeline = self._pipeline_html(phases, agg_statuses)

        # 4-column table
        tbl_id   = re.sub(r"[^\w]", "_", test_name)
        tbl_html = self._phase_table(tbl_id, label, phases, patients, patient_map)

        return f"""
<div class="flow-card" data-flow="{escape(test_name)}">
  <div class="flow-header">
    <div class="fh-left">
      <div class="flow-title">{escape(label)}</div>
      <div class="flow-meta">{meta}</div>
    </div>
    <div class="fh-right">
      <span class="flow-badge {badge_cls}">{badge_txt}</span>
      <div class="flow-phase-stat">{stat}</div>
    </div>
  </div>

  <!-- Pipeline -->
  <div class="pipeline-wrap">
    <div class="pipeline-label">Execution Pipeline</div>
    {pipeline}
  </div>

  <!-- 4-column table -->
  <div class="tbl-outer">
    <table class="phase-tbl" id="{tbl_id}">
      <thead>
        <tr>
          <th onclick="sortPhaseCol('{tbl_id}',0)">Patient<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',1)">Executed Flow<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',2)">Executed Section<span class="si">&#8597;</span></th>
          <th onclick="sortPhaseCol('{tbl_id}',3)">Status<span class="si">&#8597;</span></th>
        </tr>
      </thead>
      <tbody>
        {tbl_html}
      </tbody>
    </table>
  </div>
</div>"""

    # ---------------------------------------------------------------- pipeline
    def _aggregate_pipeline(
        self,
        phases:      List[str],
        patients:    List[str],
        patient_map: dict,
    ) -> Dict[str, str]:
        """Return worst-case status per phase across all patients."""
        agg: Dict[str, str] = {}
        for phase in phases:
            statuses = []
            for pid in patients:
                for e in patient_map.get(pid, []):
                    if e.phase_name == phase:
                        statuses.append(e.status)
            if "FAILED" in statuses:
                agg[phase] = "FAILED"
            elif statuses and all(s == "PASSED" for s in statuses):
                agg[phase] = "PASSED"
            else:
                agg[phase] = "NOT EXECUTED"
        return agg

    def _pipeline_html(
        self,
        phases:   List[str],
        statuses: Dict[str, str],
    ) -> str:
        nodes = []
        for i, phase in enumerate(phases):
            s = statuses.get(phase, "NOT EXECUTED")
            if s == "PASSED":
                cls, icon = "pn-pass", "&#10003;"
            elif s == "FAILED":
                cls, icon = "pn-fail", "&#10007;"
            else:
                cls, icon = "pn-notexec", "&#9711;"
            nodes.append(
                f'<div class="pnode {cls}" title="{escape(phase)}: {escape(s)}">'
                f'<div class="pn-icon">{icon}</div>'
                f'<div class="pn-name">{escape(phase)}</div>'
                f'</div>'
            )
            if i < len(phases) - 1:
                nodes.append('<div class="p-arrow">&rarr;</div>')
        return f'<div class="pipeline">{"".join(nodes)}</div>'

    # ---------------------------------------------------------------- table
    def _phase_table(
        self,
        tbl_id:      str,
        flow_label:  str,
        phases:      List[str],
        patients:    List[str],
        patient_map: dict,
    ) -> str:
        rows: List[str] = []
        for pid in patients:
            entry_map = {e.phase_name: e for e in patient_map.get(pid, [])}
            for phase in phases:
                entry = entry_map.get(phase)

                if entry is None:
                    status       = "NOT EXECUTED"
                    error_str    = ""
                    shot_path    = ""
                else:
                    status       = entry.status
                    error_str    = entry.error or ""
                    shot_path    = entry.screenshot_path or ""

                if status == "PASSED":
                    row_cls   = "tr-pass"
                    badge_cls = "pb-pass"
                    badge_txt = "&#10003; Passed"
                    shot_link = ""
                    if shot_path:
                        rel = Path(shot_path).as_posix()
                        shot_link = (
                            f' <a class="pshot" href="../{rel}" target="_blank"'
                            f' title="View success screenshot">&#128247;</a>'
                        )
                    status_inner = (
                        f'<span class="pbadge {badge_cls}" data-ps="{escape(status)}">'
                        f'{badge_txt}</span>{shot_link}'
                    )

                elif status == "FAILED":
                    row_cls   = "tr-fail"
                    badge_cls = "pb-fail"
                    badge_txt = "&#10007; Failed"
                    err_short = escape(error_str[:110]) + ("..." if len(error_str) > 110 else "")
                    err_full  = escape(error_str)
                    err_html  = (
                        f'<div class="err-detail">{err_short}'
                        f'{"<span class=\"err-toggle\" onclick=\"toggleErrFull(this)\"> show more</span>" if len(error_str) > 110 else ""}'
                        f'<div class="err-full-text">{err_full}</div>'
                        f'</div>'
                    ) if error_str else ""
                    shot_html = ""
                    if shot_path:
                        rel = Path(shot_path).as_posix()
                        shot_html = (
                            f'<a class="pshot" href="../{rel}" target="_blank">'
                            f'&#128247; Screenshot</a>'
                        )
                    status_inner = (
                        f'<span class="pbadge {badge_cls}" data-ps="{escape(status)}">{badge_txt}</span>'
                        f'{err_html}{shot_html}'
                    )

                else:  # NOT EXECUTED
                    row_cls   = "tr-notexec"
                    badge_cls = "pb-notexec"
                    status_inner = (
                        f'<span class="pbadge {badge_cls}" data-ps="{escape(status)}">'
                        f'&#9711; Not Executed</span>'
                    )

                display_pid = escape(patient_label(str(pid)))
                pid_raw     = escape(str(pid))
                rows.append(
                    f'<tr class="{row_cls}">'
                    f'<td class="td-pid" title="{pid_raw}">{display_pid}</td>'
                    f'<td class="td-flow">{escape(flow_label)}</td>'
                    f'<td class="td-phase">{escape(phase)}</td>'
                    f'<td class="td-status">{status_inner}</td>'
                    f'</tr>'
                )

        if not rows:
            return f'<tr><td colspan="4" class="no-phase-data">No phase data for this flow.</td></tr>'
        return "\n".join(rows)


# =============================================================================
# PATIENT PHASE JSON REPORT GENERATOR
# =============================================================================
class PatientPhaseJsonGenerator:
    """Generates a structured JSON report of per-patient, per-phase results."""

    def generate(self, phase_tracker, output_path: Path) -> None:
        from dataclasses import asdict as _asdict
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data    = phase_tracker.get_report_data()
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "tests": [],
        }
        for test_name, patient_map in data.items():
            phases   = phase_tracker.phases_for_test(test_name)
            patients = phase_tracker.patients_for_test(test_name)
            test_block = {
                "test_name":  test_name,
                "flow_label": _FLOW_LABELS.get(test_name, test_name),
                "phases":     phases,
                "patients":   [],
            }
            for pid in patients:
                entries = patient_map.get(pid, [])
                test_block["patients"].append({
                    "patient_id": pid,
                    "phases": [_asdict(e) for e in entries],
                })
            payload["tests"].append(test_block)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# =============================================================================
# MODULE-LEVEL SINGLETONS
# =============================================================================
artifact_manager     = ArtifactManager()
report_registry      = ReportRegistry()
html_generator       = HtmlReportGenerator()
json_generator       = JsonReportGenerator()
csv_generator        = CsvReportGenerator()
phase_html_generator = PatientPhaseHtmlGenerator()
phase_json_generator = PatientPhaseJsonGenerator()

# Public helpers for conftest.py (session management)
__all__ = [
    # paths / constants
    "SUMMARY_HTML", "SUMMARY_JSON", "SUMMARY_CSV",
    "PATIENT_PHASE_HTML", "PATIENT_PHASE_JSON",
    "ALLURE_RESULTS_DIR", "ALLURE_HTML_DIR",
    "SCREENSHOTS_SUCCESS_DIR", "SCREENSHOTS_FAILURES_DIR",
    "SESSION_REGISTRY_PATH", "SESSIONS_PER_BATCH",
    # session helpers
    "register_session", "get_batch_number",
    "resolve_report_paths", "load_batch_sessions",
    "save_run_snapshot",
    # singletons
    "artifact_manager", "report_registry",
    "html_generator", "json_generator", "csv_generator",
    "phase_html_generator", "phase_json_generator",
]
