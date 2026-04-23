# -*- coding: utf-8 -*-
"""
Loader for .claude/test_run_session.json — the test→patient→scenario map.

Used by the stakeholder report to enrich the scenario column with human-readable
descriptions. Returns an empty dict on any IO/JSON error so report generation
never fails on a missing or malformed session file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

SESSION_JSON_PATH = Path(".claude") / "test_run_session.json"

_cache: Dict[str, dict] = {}
_loaded: bool = False


def load_session_context() -> Dict[str, dict]:
    """Return the parsed session JSON (cached). `{}` on any failure."""
    global _cache, _loaded
    if _loaded:
        return _cache
    try:
        _cache = json.loads(SESSION_JSON_PATH.read_text(encoding="utf-8"))
    except (IOError, OSError, json.JSONDecodeError):
        _cache = {}
    _loaded = True
    return _cache


def scenario_for(test_name: str) -> str:
    """Return the scenario description for a test, or '' if unavailable."""
    ctx = load_session_context()
    return (
        ctx.get("e2e_assignments", {})
           .get(test_name, {})
           .get("scenario", "")
    )


def marker_for(test_name: str) -> str:
    """Return the pytest marker recorded for a test, or 'uncategorised'."""
    ctx = load_session_context()
    return (
        ctx.get("e2e_assignments", {})
           .get(test_name, {})
           .get("marker", "")
    ) or "uncategorised"


def patient_label_from_session(patient_id: str) -> str:
    """Return the patient display name from _patient_map, or '' if unavailable."""
    ctx = load_session_context()
    entry = ctx.get("_patient_map", {}).get(patient_id, {})
    return entry.get("name", "") or entry.get("display_name", "") or ""
