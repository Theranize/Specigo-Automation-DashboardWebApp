# Super-User (admin/manager) E2E Runner

Single-session test runner that drives any combination of the five role tasks
(FD → Phlebotomist → Accession → Lab Technician → Doctor) under one
`admin` or `manager` login, optionally handing off to per-role users at a
configurable stop-point.

Full design and grammar reference: **`docs/role_session.md`**.

## Files

| File | Purpose |
|---|---|
| `test_super_user_e2e.py` | Parameterized entry test. Empty parametrize when `--super-targets` is absent → zero items collected. |
| `_manifest.py`           | `PATIENT_MANIFESTS[pid]` — builders that lift each canonical P-test into a list of `PhaseStep` objects tagged with `(stage, kind, role)`. |

The orchestrator (`flows/super_user_orchestrator.py`) walks the manifest,
swaps logins at role boundaries via the `swap_user` fixture, and honours the
`till X / continue / till Y / +reassign-*` scope semantics from the plan.

## Quick examples (driven from `run.bat`)

```bat
run admin P1                                            rem admin owns all 5 phases of P1
run admin P1 till acc continue                          rem admin: FD/Phlebo/Acc; per-role: LT, Doctor
run admin P2 till acc continue till doc                 rem admin to acc; per-role to first doctor
run admin P2 till acc continue till doc +reassign-admin rem admin claws back reassign/recollect inside continuation
run admin P2 +reassign-users                            rem admin owns everything except reassign/recollect
run admin e2e staging 3                                 rem all 14 patients, super-user-everything, staging, 3 workers
run manager P5 P8 till doc continue staging 2
```

## Adding a new patient

1. Add a builder `_build_pN(pid)` in `_manifest.py` that returns a `list[PhaseStep]`.
2. Register it in `PATIENT_MANIFESTS`.
3. Add a `test_super_user_pN` entry in `utils/reporting/constants.py::FLOW_REGISTRY`
   (mirror the canonical patient's `phase_order`).
4. Add the matching `e2e_assignments` entry in `.claude/test_run_session.json`.
