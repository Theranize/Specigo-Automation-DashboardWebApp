# -*- coding: utf-8 -*-
"""Shared per-phase per-role runner for parametrized E2E tests.

Used by:
  - tests/e2e/acceptance/test_e2e_acceptance.py
  - tests/e2e/rejection/test_e2e_rejection.py

Each calls `run_patient(page, login_as, pid)` once per parametrized patient.
The runner walks that patient's manifest from `tests/e2e/_manifest.py`,
logs in fresh for every role boundary, wraps each step in
`phase_tracker.track(...)`, and honours per-step `success_predicate` overrides
for error-test patients (P7, P11).
"""
from __future__ import annotations

import pytest

from utils.phase_tracker import phase_tracker
from flows.logout_flow import execute_logout
from tests.e2e._manifest import PATIENT_MANIFESTS, PATIENT_TEST_KEYS


def _logout(page) -> None:
    """Logout + return to /login (mirrors the legacy per-test _logout helper)."""
    try:
        execute_logout(page)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle")
        page.goto(page.context.base_url + "login")
        page.wait_for_load_state("networkidle")
    except Exception:
        pass


def run_patient(page, login_as, pid: str) -> None:
    """Drive a patient's manifest one phase at a time, swapping logins per role.

    `login_as` is the existing per-test fixture (fixtures/session_fixtures.py).
    On teardown it logs out and clears runtime_state, so we don't need to
    duplicate that here — we only handle mid-test role swaps.
    """
    if pid not in PATIENT_MANIFESTS:
        pytest.fail(f"[{pid}] no manifest registered in tests/e2e/_manifest.py")

    test_key = PATIENT_TEST_KEYS[pid]
    steps    = PATIENT_MANIFESTS[pid](pid)
    cur_role: str | None = None

    print(f"\n[{pid}] e2e run: phases={len(steps)} test_key={test_key}")

    for idx, step in enumerate(steps, 1):
        if step.role != cur_role:
            if cur_role is not None:
                _logout(page)
            login_as(step.role)
            cur_role = step.role

        with phase_tracker.track(page, pid, step.label, test_key):
            print(f"[{pid}] phase {idx:2}/{len(steps)}: {step.label}  (role={step.role})")
            r = step.runner(page)
            if step.success_predicate is not None:
                if not step.success_predicate(r):
                    pytest.fail(
                        f"[{pid}] {step.label}: success_predicate returned False; "
                        f"result={r}"
                    )
            else:
                if r.get("error_found"):
                    pytest.fail(f"[{pid}] {step.label}: {r.get('error_message')}")
                assert r.get("completed"), (
                    f"[{pid}] {step.label}: step did not complete"
                )
