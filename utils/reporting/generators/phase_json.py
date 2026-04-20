# -*- coding: utf-8 -*-
"""PatientPhaseJsonGenerator — produces patient_phase_report[N].json."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from utils.reporting.constants import flow_label


class PatientPhaseJsonGenerator:
    """Generates a structured JSON report of per-patient, per-phase results."""

    def generate(self, phase_tracker, output_path: Path) -> None:
        """Write phase breakdown JSON to *output_path*."""
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
                "flow_label": flow_label(test_name),
                "phases":     phases,
                "patients":   [],
            }
            for pid in patients:
                entries = patient_map.get(pid, [])
                test_block["patients"].append({
                    "patient_id": pid,
                    "phases": [asdict(e) for e in entries],
                })
            payload["tests"].append(test_block)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
