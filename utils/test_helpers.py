# -*- coding: utf-8 -*-
"""
Test utility helpers.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

from typing import List

import pytest


def smart_parametrize(argname: str, ids: List[str]):
    """
    Return a pytest.mark.parametrize decorator for the given IDs.

    Always parametrizes — test shows as test_fn[P1], test_fn[P2] etc.
    Compatible with pytest 9.x which rejects default values on parametrized args.

    Usage in test files:
        PATIENT_IDS = [p["patient_id_ref"] for p in DATA["patients"]]

        @pytest.mark.regression
        @smart_parametrize("patient_id", PATIENT_IDS)
        def test_something(page, login_as, patient_id):
            ...

    When you add P2, P3 … to the JSON, the loop activates automatically.
    No test-file changes required for the multi-patient case.
    """
    return pytest.mark.parametrize(argname, ids)
