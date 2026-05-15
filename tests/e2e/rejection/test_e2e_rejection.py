# -*- coding: utf-8 -*-
"""E2E rejection runner — parametrized over every patient whose
`primary_file` is `rejection` in `.claude/test_run_session.json::patients`.

Adding a new rejection patient: add the entry to `patients` and write a
`_build_pN(pid)` function in `tests/e2e/_manifest.py`. No edit here is needed.

Markers (e2e/rejection/rectification/...) are applied per parametrize item
from each patient's `markers` list, so `-m "e2e and rectification"` continues
to pick up cross-cutting cases (e.g. P10) without per-file rewiring.
"""
from __future__ import annotations

import pytest

from tests.e2e._manifest import PATIENT_MANIFESTS, patient_catalog, patients_for_file
from tests.e2e._runner import run_patient

_FILE_KEY = "rejection"


def pytest_generate_tests(metafunc) -> None:
    if "pid" not in metafunc.fixturenames:
        return
    cat = patient_catalog()
    params = []
    for pid in patients_for_file(_FILE_KEY):
        if pid not in PATIENT_MANIFESTS:
            continue
        marks = [getattr(pytest.mark, m) for m in cat[pid].get("markers", [])]
        params.append(pytest.param(pid, marks=marks, id=pid))
    metafunc.parametrize("pid", params)


def test_e2e_rejection(page, login_as, pid: str) -> None:
    """Drive one rejection patient's manifest with per-phase per-role login."""
    run_patient(page, login_as, pid)
