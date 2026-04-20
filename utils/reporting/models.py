# -*- coding: utf-8 -*-
"""TestResult dataclass — the core data model for the reporting package."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# =============================================================================
# CONSTANTS
# =============================================================================
_EMPTY = ""


# =============================================================================
# DATA MODEL
# =============================================================================
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
