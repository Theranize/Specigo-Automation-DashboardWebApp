# -*- coding: utf-8 -*-
"""Super-user orchestrator: walk a per-patient phase manifest, swap logins at
role boundaries, and honour `till X / continue / till Y` scope semantics.

Plan reference: docs/role_session.md §5.3.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal, Optional

import pytest

from utils.phase_tracker import phase_tracker

# --- types and constants -----------------------------------------------------

Stage = Literal["fd", "phlebo", "acc", "labt", "doc"]
Kind  = Literal["primary", "reassign", "recollect"]

#: Canonical stage order used for "till X" / "continue till Y" comparisons.
STAGE_ORDER: dict = {"fd": 1, "phlebo": 2, "acc": 3, "labt": 4, "doc": 5}


@dataclass
class PhaseStep:
    """One executable step in a patient's super-user manifest.

    Fields:
      label  — phase_tracker label; must match a FLOW_REGISTRY phase entry.
      stage  — canonical stage bucket for till/continue evaluation.
      kind   — primary | reassign | recollect (drives +reassign-* overrides).
      role   — base per-role login key for fallback (front_desk, etc.).
      runner — callable(page) -> dict with keys {completed, error_found,
               error_message, ...}. The orchestrator calls this inside a
               phase_tracker.track(...) block.
    """
    label:  str
    stage:  Stage
    kind:   Kind
    role:   str
    runner: Callable[[object], dict]


@dataclass
class ScopeSpec:
    """Parsed CLI scope for a single super-user run.

    Fields:
      super_role     — "admin" | "manager".
      until          — `till X` stop-stage (None ⇒ super-user owns everything).
      has_continue   — True iff `continue` keyword was present.
      continue_until — `continue till Y` cap stage (None ⇒ continue to natural end).
      reassign_owner — explicit override:
                       "super" → +reassign-admin (claw-back into continuation)
                       "users" → +reassign-users (carve-out from full scope)
                       "default" → use scope-dependent default (see plan §4 table).
    """
    super_role:     str
    until:          Optional[Stage] = None
    has_continue:   bool = False
    continue_until: Optional[Stage] = None
    reassign_owner: Literal["super", "users", "default"] = "default"


# --- ownership decision ------------------------------------------------------

def owner_for(step: PhaseStep, spec: ScopeSpec, in_continuation: bool) -> str:
    """Decide who runs a step. Returns "super" or "users".

    Defaults:
      pre-handoff (in_continuation=False)  → super-user owns everything;
                                             +reassign-users carves out R/RC.
      post-handoff (in_continuation=True)  → per-role users own everything;
                                             +reassign-admin claws back R/RC.
    """
    if not in_continuation:
        if step.kind in ("reassign", "recollect") and spec.reassign_owner == "users":
            return "users"
        return "super"
    if step.kind in ("reassign", "recollect") and spec.reassign_owner == "super":
        return "super"
    return "users"


# --- orchestrator engine -----------------------------------------------------

def run(
    page,
    swap_user: Callable[[object, str], None],
    pid: str,
    steps: List[PhaseStep],
    spec: ScopeSpec,
    test_key: str,
) -> None:
    """Walk the trace, swap users at role boundaries, honour terminators.

    `swap_user` is the `swap_user` fixture's callable.
    `test_key` is the FLOW_REGISTRY key for this super-user variant
    (e.g. "test_super_user_p1") so phase_tracker can resolve phase_order.
    """
    in_continuation = False
    cur_role: Optional[str] = None
    until_idx = STAGE_ORDER[spec.until] if spec.until else None
    cont_until_idx = STAGE_ORDER[spec.continue_until] if spec.continue_until else None

    for step in steps:
        owner = owner_for(step, spec, in_continuation)
        target_role = spec.super_role if owner == "super" else step.role

        if target_role != cur_role:
            swap_user(page, target_role)
            cur_role = target_role

        with phase_tracker.track(page, pid, step.label, test_key):
            r = step.runner(page)
            if r.get("error_found"):
                pytest.fail(f"[{pid}] {step.label}: {r.get('error_message')}")
            assert r.get("completed"), f"[{pid}] {step.label}: step did not complete"

        step_idx = STAGE_ORDER[step.stage]

        # Bare `till X` (no continue) ⇒ terminate at first step that hits X.
        if (not in_continuation
                and not spec.has_continue
                and until_idx is not None
                and step_idx >= until_idx):
            return

        # `till X continue …` ⇒ enter continuation window after first step that hits X.
        if (not in_continuation
                and spec.has_continue
                and until_idx is not None
                and step_idx >= until_idx):
            in_continuation = True
            continue

        # In continuation: stop at first step whose stage hits continue_until.
        if (in_continuation
                and cont_until_idx is not None
                and step_idx >= cont_until_idx):
            return
