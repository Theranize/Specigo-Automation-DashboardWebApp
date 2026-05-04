# -*- coding: utf-8 -*-
"""Super-user (admin/manager) entry test.

Parameterizes over the patient IDs supplied via `--super-targets`. With the
flag absent, parametrize is empty → pytest collects ZERO items → existing
discovery is unchanged.

Plan reference: docs/role_session.md §5.1.
"""
from __future__ import annotations

import pytest

from flows.super_user_orchestrator import ScopeSpec, run as orchestrator_run
from tests.e2e.super_user._manifest import PATIENT_MANIFESTS, SUPER_USER_TEST_KEYS


def pytest_generate_tests(metafunc) -> None:
    """Parametrize `pid` from --super-targets; empty when flag is unset."""
    if "pid" not in metafunc.fixturenames:
        return
    raw = metafunc.config.getoption("--super-targets", default=None)
    if not raw:
        metafunc.parametrize("pid", [], ids=[])
        return
    pids = [p.strip().upper() for p in raw.split(",") if p.strip()]
    invalid = [p for p in pids if p not in PATIENT_MANIFESTS]
    if invalid:
        raise pytest.UsageError(
            f"Unknown super-user target(s): {', '.join(invalid)}. "
            f"Valid: {', '.join(PATIENT_MANIFESTS.keys())}"
        )
    metafunc.parametrize("pid", pids, ids=pids)


@pytest.mark.e2e
def test_super_user_e2e(page, swap_user, pytestconfig, pid: str) -> None:
    """Drive one patient flow as admin/manager per the parsed scope spec."""
    super_as       = pytestconfig.getoption("--super-as")
    until          = pytestconfig.getoption("--super-until")
    has_continue   = pytestconfig.getoption("--super-continue")
    continue_until = pytestconfig.getoption("--super-continue-till")
    reassign_owner = pytestconfig.getoption("--super-reassign")

    spec = ScopeSpec(
        super_role     = super_as,
        until          = until,
        has_continue   = has_continue,
        continue_until = continue_until,
        reassign_owner = reassign_owner,
    )

    steps    = PATIENT_MANIFESTS[pid](pid)
    test_key = SUPER_USER_TEST_KEYS[pid]

    print(f"\n[{pid}] super-user run: role={super_as} until={until} "
          f"continue={has_continue} continue_till={continue_until} "
          f"reassign={reassign_owner} steps={len(steps)}")

    orchestrator_run(page, swap_user, pid, steps, spec, test_key)
