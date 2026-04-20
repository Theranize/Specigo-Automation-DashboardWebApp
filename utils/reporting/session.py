# -*- coding: utf-8 -*-
"""
Session registry, run snapshot persistence, and batch management.

Functions here are responsible for all file I/O related to session tracking.
Failures are surfaced via warnings.warn so they appear in pytest output
without aborting the session.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import json
import warnings
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from utils.reporting.constants import (
    REPORTS_ROOT,
    RUNS_DIR,
    SESSION_REGISTRY_PATH,
    SESSIONS_PER_BATCH,
    SUMMARY_HTML,
    SUMMARY_JSON,
    SUMMARY_CSV,
)


# =============================================================================
# RUN SNAPSHOTS
# =============================================================================

def save_run_snapshot(
    run_id:      str,
    summary:     dict,
    results:     list,
    session_num: int            = 0,
    phase_data:  Optional[dict] = None,
) -> None:
    """Persist this run's summary, results, and phase data to reports/runs/<run_id>.json."""
    try:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        serialised = [
            asdict(r) if hasattr(r, "__dataclass_fields__") else dict(r)
            for r in results
        ]
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
    except Exception as exc:
        warnings.warn(
            f"[reporting] Failed to save run snapshot '{run_id}': {exc}",
            stacklevel=2,
        )


def _load_run_history() -> List[dict]:
    """Load all saved run snapshots in chronological order."""
    if not RUNS_DIR.exists():
        return []
    runs: List[dict] = []
    for f in sorted(RUNS_DIR.glob("run_*.json")):
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as exc:
            warnings.warn(
                f"[reporting] Could not read run snapshot '{f.name}': {exc}",
                stacklevel=2,
            )
    return runs


# =============================================================================
# SESSION REGISTRY  –  persistent session counter & metadata
# =============================================================================

def load_session_registry() -> dict:
    """Load the session registry; returns an empty structure if file absent or corrupt."""
    if SESSION_REGISTRY_PATH.exists():
        try:
            return json.loads(SESSION_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.warn(
                f"[reporting] Session registry corrupt or unreadable: {exc}",
                stacklevel=2,
            )
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


# =============================================================================
# BATCH MANAGEMENT
# =============================================================================

def get_batch_number(session_num: int) -> int:
    """Return the 1-based batch index for *session_num* (SESSIONS_PER_BATCH per batch)."""
    return (session_num - 1) // SESSIONS_PER_BATCH + 1


def resolve_report_paths(batch: int) -> Tuple[Path, Path, Path, Path, Path]:
    """
    Return (summary_html, summary_json, summary_csv, phase_html, phase_json).

    Summary reports are cumulative across ALL sessions — always the same file.
    Phase reports rotate per batch (batch 1 → default names, batch 2+ → numeric suffix).
    """
    suffix = "" if batch == 1 else str(batch)
    return (
        SUMMARY_HTML,
        SUMMARY_JSON,
        SUMMARY_CSV,
        REPORTS_ROOT / f"patient_phase_report{suffix}.html",
        REPORTS_ROOT / f"patient_phase_report{suffix}.json",
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
                snap.setdefault("session_num",    meta.get("session_num", 0))
                snap.setdefault("start_time",     meta.get("start_time", ""))
                snap.setdefault("end_time",       meta.get("end_time", ""))
                snap.setdefault("tests_executed", meta.get("tests_executed", []))
                result.append(snap)
            except Exception as exc:
                warnings.warn(
                    f"[reporting] Could not load batch session '{run_id}': {exc}",
                    stacklevel=2,
                )
        else:
            # Snapshot file missing — synthesise from registry metadata
            fallback = dict(meta)
            fallback.setdefault("phase_data", {})
            fallback.setdefault("results",    [])
            result.append(fallback)
    return result
