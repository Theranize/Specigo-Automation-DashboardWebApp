# -*- coding: utf-8 -*-
"""CsvReportGenerator — produces summary_report.csv."""
from __future__ import annotations

import csv as _csv
from io import StringIO
from pathlib import Path
from typing import List

from utils.reporting.models import TestResult


class CsvReportGenerator:
    """Generates a flat CSV report suitable for Excel / CI parsing."""

    _HEADERS = [
        "Test Name", "Module", "Patient ID", "Status",
        "Error", "Screenshot", "Duration (s)", "Timestamp",
    ]

    def generate(self, results: List[TestResult], output_path: Path) -> None:
        """Write result rows to *output_path* as UTF-8 BOM CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        buf    = StringIO()
        writer = _csv.writer(buf, quoting=_csv.QUOTE_ALL, lineterminator="\n")
        writer.writerow(self._HEADERS)
        for r in results:
            writer.writerow([
                r.test_name, r.module, r.patient_id, r.status,
                r.error, r.screenshot_path, r.duration, r.timestamp,
            ])
        output_path.write_text(buf.getvalue(), encoding="utf-8-sig")
