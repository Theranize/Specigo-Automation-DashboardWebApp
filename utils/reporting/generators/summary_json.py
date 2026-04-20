# -*- coding: utf-8 -*-
"""JsonReportGenerator — produces summary_report.json."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List

from utils.reporting.models import TestResult


class JsonReportGenerator:
    """Generates a structured JSON report of the current test session."""

    def generate(
        self,
        results:     List[TestResult],
        summary:     dict,
        output_path: Path,
    ) -> None:
        """Write summary + results to *output_path* as JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "results": [asdict(r) for r in results]}
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
