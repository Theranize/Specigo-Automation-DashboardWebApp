# -*- coding: utf-8 -*-
"""
ArtifactManager and ReportRegistry — session-scoped in-memory singletons.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import List

from utils.reporting.constants import (
    SCREENSHOTS_DIR,
    SCREENSHOTS_SUCCESS_DIR,
    SCREENSHOTS_FAILURES_DIR,
    TRACES_DIR,
    LOGS_DIR,
    VIDEOS_DIR,
    HTML_REPORT_DIR,
    JSON_REPORT_DIR,
    ALLURE_RESULTS_DIR,
    ALLURE_HTML_DIR,
    REPORTS_ROOT,
)
from utils.reporting.models import TestResult, _EMPTY


# =============================================================================
# ARTIFACT MANAGER
# =============================================================================
class ArtifactManager:
    """Manages directory structure and canonical file paths for test artifacts."""

    @staticmethod
    def _sanitize(name: str) -> str:
        """Strip characters unsafe in filesystem path components."""
        return re.sub(r"[^\w\-]", "_", str(name))

    def ensure_dirs(self) -> None:
        """Create all artifact and report directories."""
        for d in (
            SCREENSHOTS_DIR, SCREENSHOTS_SUCCESS_DIR, SCREENSHOTS_FAILURES_DIR,
            TRACES_DIR, LOGS_DIR, VIDEOS_DIR,
            HTML_REPORT_DIR, JSON_REPORT_DIR,
            ALLURE_RESULTS_DIR, ALLURE_HTML_DIR,
            REPORTS_ROOT,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def screenshot_path(self, test_name: str, patient_id: str, step: str) -> Path:
        """Return canonical path for a test-level screenshot."""
        dest = (
            SCREENSHOTS_DIR
            / self._sanitize(test_name)
            / "patients"
            / self._sanitize(patient_id)
        )
        dest.mkdir(parents=True, exist_ok=True)
        return dest / f"{self._sanitize(step)}.png"

    def trace_path(self, test_name: str) -> Path:
        """Return canonical path for a Playwright trace ZIP."""
        TRACES_DIR.mkdir(parents=True, exist_ok=True)
        return TRACES_DIR / f"{self._sanitize(test_name)}.zip"

    def log_path(self, test_name: str) -> Path:
        """Return canonical path for a test log file."""
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return LOGS_DIR / f"{self._sanitize(test_name)}.log"

    def video_path(self, patient: str, flowname: str) -> Path:
        """
        Return the destination path for a session video.

        Naming format: {patient}-{flowname}.webm
        Example: P1-acceptanceflow.webm
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
        """Append a new test result entry."""
        def _norm(v: str) -> str:
            return _EMPTY if v in ("---", "\u2014", "-") else (v or _EMPTY)

        self._results.append(
            TestResult(
                test_name=test_name,
                module=module,
                patient_id=patient_id,
                status=status,
                error=_norm(error),
                screenshot_path=_norm(screenshot_path),
                duration=round(duration, 2),
            )
        )

    def results(self) -> List[TestResult]:
        """Return a copy of all collected results."""
        return list(self._results)

    def extend_from_dicts(self, payload: list) -> None:
        """Append TestResults reconstructed from dicts (xdist worker partials).

        Unknown keys are dropped so future TestResult field additions don't
        crash on stale partials.
        """
        allowed = set(TestResult.__dataclass_fields__.keys())
        for d in payload or []:
            if isinstance(d, dict):
                self._results.append(TestResult(**{k: v for k, v in d.items() if k in allowed}))

    def summary(self) -> dict:
        """Return an aggregated summary dict for the current session."""
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
