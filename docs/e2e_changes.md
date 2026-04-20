# E2E Test Suite — Changes & Design Decisions

> Records all structural changes made to the E2E test suite. Read this to understand why the suite is structured the way it is before adding or modifying tests.

---

## 1. Patient Roster Expansion (P1–P14)

The suite expanded from 6 prototype patients (P1–P5 + BC) to 14 fully distinct patients, each mapped to a specific scenario and DDT entry.

| # | Test File | Patient | Scenario | Type | Date |
|---|-----------|---------|----------|------|------|
| P1  | `test_e2e_acceptance.py` | Aditya Kumar Mishra (7777777777) | Full acceptance — all 7 tests, all stages (FD→Phlebo→Acc→LT→Doctor) | existing | global |
| P2  | `test_e2e_p2_rejection.py` | Aditya Kumar Mishra (7777777777) | 3-cycle rejection — Acc:Serum → LT:24h urine → Dr:LFT resample → partial_approve | existing | global |
| P3  | `test_e2e_p3_partial_approve.py` | Aditya Kumar Mishra (7777777777) | Partial pipeline — phlebo 3/4, acc 2/3, LT 1/2 (Serum), Dr approves RFT+LFT | existing | global |
| P4  | `test_e2e_p4_rectification.py` | Aditya Kumar Mishra (7777777777) | Full acceptance + Dr rectifies RFT+LFT | existing | global |
| P5  | `test_e2e_p5_relative_acceptance.py` | Sunita Kumari Mishra (8839900148) | Select existing relative (Wife) — full acceptance, all 7 tests | existing_relative | global |
| P6  | `test_e2e_p6_rejection.py` | Aditya Kumar Mishra (7777777777) | 3-cycle rejection — Acc:Urine → LT:Serum → Dr:CBC resample → full approve | existing | global |
| P7  | `test_e2e_p7_limit_error.py` | (8839900148 account) | Add-relative limit error — 10-patient cap reached | existing | N/A |
| P8  | `test_e2e_p8_new_patient_acceptance.py` | Priya Sharma (8900000005) | New user — full acceptance, all 7 tests | new | global |
| P9  | `test_e2e_p9_new_patient_rejection.py` | Rohan Desai (8900000006) | New user — 3-cycle rejection → LFT resample → full approve | new | global |
| P10 | `test_e2e_p10_new_patient_partial.py` | Kavita Nair (8900000007) | New user — Acc:24h urine, full LT, Dr approve all + rectify LFT | new | global |
| P11 | `test_e2e_p10_duplicate_mobile_error.py` | Rajesh Kumar (9999999999) | Duplicate mobile error — new patient form with already-registered number | new | N/A |
| P12 | `test_e2e_p12_relative_acceptance.py` | Vikram Kumar Mishra (7777777777) | Add new relative (Brother) — full acceptance + Dr rectify RFT+LFT | new_relative | global |
| P13 | `test_e2e_p13_partial_rejection.py` | Aditya Kumar Mishra (7777777777) | 2-cycle rejection — Acc:Serum, LT:24h urine, Dr approves all (no resample) | existing | local 16/04/2026 |
| P14 | `test_e2e_p14_partial_approve.py` | Sanjay Mehta (8900000008) | New user — 3 tests (CBC+RFT+LFT), partial LT params, Dr partial_approve all 3 | new | global |

**Rule:** Patient IDs live only in `.claude/test_run_session.json`. Test files always read `pid = SESSION["e2e_assignments"][_TEST]["patient_id"]` — never hardcode `pid = "PX"` in any `.py` file.

---

## 2. New Test Files Created

Seven new test files were created during this session to complete the P2–P14 coverage:

### Acceptance (`tests/e2e/acceptance/`)

| File | Patient | Phases |
|------|---------|--------|
| `test_e2e_p3_partial_approve.py` | P3 | 5: FD → Phlebo → Acc (2 samples) → LT (Serum only, saves RFT+LFT) → Doctor (approve RFT+LFT) |
| `test_e2e_p14_partial_approve.py` | P14 | 5: FD → Phlebo → Acc → LT (partial params) → Doctor (partial_approve CBC+RFT+LFT) |

### Rejection (`tests/e2e/rejection/`)

| File | Patient | Phases | Rejection Pattern |
|------|---------|--------|-------------------|
| `test_e2e_p2_rejection.py` | P2 | 17 | Acc:Serum → Phlebo recollect → Acc re-accept → LT:24h urine → Acc reassign → Phlebo recollect → Acc re-accept → LT save all → Dr resample LFT → Acc reassign → Phlebo recollect → Acc re-accept → LT save LFT → Dr partial_approve |
| `test_e2e_p6_rejection.py` | P6 | 17 | Same 3-cycle structure as P2 but: Acc:Urine, LT:Serum, Dr:CBC resample, final full approve |
| `test_e2e_p9_new_patient_rejection.py` | P9 | 17 | Same structure as P2 (new user Rohan Desai), final full approve LFT |
| `test_e2e_p10_new_patient_partial.py` | P10 | 9 | 1-cycle: Acc:24h urine → recollect → re-accept → LT full → Dr approve all → Dr rectify LFT |
| `test_e2e_p13_partial_rejection.py` | P13 | 12 | 2-cycle: Acc:Serum + LT:24h urine → no doctor resample → Dr approve all. Local date 16/04/2026 |

---

## 3. DDT Pattern Changes (Old vs New)

### Old pattern (bc_combined, b1/b2/b3/b4)
```python
# Sub-keyed rejection entry in accession DDT
ac_e["rejection"]["cycles"][0]

# Sub-keyed resample entry in doctor DDT
doc_e["resample"]["tests"][0]
```

### New pattern (P2–P14)
```python
# Flat top-level entry; rejection inline in main ac_e
ac_e                            # initial reject entry
ac_e["re_accept"][0]            # re-accept after recollection
_with_pid(ac_e["re_accept"][0], pid)  # inject patient_id_ref for flow

# Doctor resample is inline in main doc_e
doc_e                           # may include resample action inline
doc_e["re_approval"]            # final approve/partial_approve after resample
_with_pid(doc_e["re_approval"], pid)  # inject patient_id_ref
```

### LT rejection phase (initial reject — NO tests called)
```python
# Only search; no test execution — rejection happens at sample acceptance level
ls_r = execute_labtech_search(page, lt_e)
# NO execute_labtech_tests here

# After recollection — both search + tests
ls2_r = execute_labtech_search(page, lt_e["re_cycles"][0])
lt2_r = execute_labtech_tests(page,  lt_e["re_cycles"][0])
```

---

## 4. DDT Field Conventions (Informational Fields)

These fields appear in DDT JSON files and `test_run_session.json` but are **never read by flow or page code**:

| Field | Location | Purpose |
|-------|----------|---------|
| `scenario` | DDT patient entries | Human description of what this entry tests — for devs only |
| `scenario_tag` | `_patient_map` in `test_run_session.json` | Machine-readable tag for documentation — not used in code |

**Date override** works automatically via `resolve_filters(patient_entry)` in `utils/date_utils.py`:
```python
return patient_entry.get("filters") or _CFG["filters"]
```
Presence of a `"filters"` key in the DDT entry is sufficient. P13 carries a local `"filters"` override; all other patients use the global `config/test_config.yaml` value. No extra tags or flags are needed.

---

## 5. B4 Test Removal

`test_e2e_b4_add_relative_rectification.py` was removed from the active suite.

**Reason:** b4 duplicated the P5 relative-selection flow and added a doctor rectify phase that is now covered by P10 and P12. Running b4 would create a second entry for P5 in reports, causing confusion and redundant test time.

**Safe to remove — zero side effects confirmed:**
- `utils/reporting/constants.py` FLOW_REGISTRY uses `.get()` with fallbacks — missing entry is harmless
- `test_data/doctor/doctor_rectify_actions.json` P5 entry was only used by b4
- No Python file outside b4 itself imports or references it

**Files cleaned up:**
- `tests/e2e/acceptance/test_e2e_b4_add_relative_rectification.py` — deleted
- `.claude/test_run_session.json` — `test_e2e_b4_add_relative_rectification` entry removed
- `utils/reporting/constants.py` — `test_e2e_b4_add_relative_rectification` entry removed from `FLOW_REGISTRY`
- `test_data/doctor/doctor_rectify_actions.json` — P5 entry removed

---

## 6. Four-Case E2E Run Scheme

The suite can be run in four targeted slices using pytest markers:

| Case | Description | Patients | Command |
|------|-------------|----------|---------|
| 1 | **All** — every active E2E test | P1–P14 | `pytest tests/e2e/ -m e2e -v` |
| 2 | **Acceptance** — full and partial acceptance flows (no rejection cycles) | P1, P3, P4, P5, P7, P8, P11, P12, P14 | `pytest tests/e2e/ -m acceptance -v` |
| 3 | **Rejection** — all rejection flows (full 3-cycle + partial) | P2, P6, P9, P10, P13 | `pytest tests/e2e/ -m rejection -v` |
| 4 | **Rectification** — flows that include a doctor rectify phase | P4, P10, P12 | `pytest tests/e2e/ -m rectification -v` |

**Notes:**
- Case 4 deliberately overlaps cases 2 and 3. P4/P12 are acceptance tests that also rectify; P10 is a rejection test that also rectifies.
- Running `-m rectification` is a targeted slice for rectification-only verification without running the full rejection or acceptance suites.

### Verify with `--collect-only`
```bash
.\Test\Scripts\pytest.exe tests/e2e/ -m e2e          --collect-only  # all 14
.\Test\Scripts\pytest.exe tests/e2e/ -m acceptance   --collect-only  # P1,P3,P4,P5,P7,P8,P11,P12,P14
.\Test\Scripts\pytest.exe tests/e2e/ -m rejection    --collect-only  # P2,P6,P9,P10,P13
.\Test\Scripts\pytest.exe tests/e2e/ -m rectification --collect-only # P4,P10,P12
```

---

## 7. New `rectification` Pytest Marker

Added a new marker so the rectification slice can be run independently.

**Registration:**
- `pytest.ini` `[markers]` section: `rectification: Flows that include a doctor rectify phase`
- `conftest.py` `pytest_configure`: `"rectification: Flows that include a doctor rectify phase"` added to `_MARKERS`

**Tests that carry `@pytest.mark.rectification`:**

| File | Existing markers | New marker |
|------|-----------------|------------|
| `tests/e2e/acceptance/test_e2e_p4_rectification.py` | `e2e`, `acceptance` | `rectification` |
| `tests/e2e/acceptance/test_e2e_p12_relative_acceptance.py` | `e2e`, `acceptance` | `rectification` |
| `tests/e2e/rejection/test_e2e_p10_new_patient_partial.py` | `e2e`, `rejection` | `rectification` |

---

## 8. Session Reference File

`.claude/test_run_session.json` has three sections:

| Section | Purpose |
|---------|---------|
| `e2e_assignments` | Maps test name → `patient_id`, `scenario`, `marker`, `path`, `ddt`. Read at test start. |
| `_patient_map` | Full patient profile per PID (name, mobile, type, scenario_tag). Informational. |
| `_patient_summary` | Quick-scan table: No \| Scenario \| Type \| Date. Informational. |

---

## 9. Legacy Tests (kept but superseded)

These files remain for historical reference but are superseded by the P-numbered test suite:

| File | Status | Superseded by |
|------|--------|---------------|
| `test_e2e_b1_accession_rejection.py` | Kept (legacy) | P2, P6, P9, P13 |
| `test_e2e_b2_labtech_rejection.py` | Kept (legacy) | P2, P6, P9, P13 |
| `test_e2e_b3_doctor_resample.py` | Kept (legacy) | P2, P6, P9 |
| `test_e2e_bc_combined_rejection.py` | Kept (legacy) | P2, P6, P9, P13 |
| `test_e2e_b4_add_relative_rectification.py` | **Removed** | P10, P12 |
