# Playwright Automation — CLAUDE.md

## Project Overview
End-to-end test automation for a multi-role clinical lab system (Specigo). Built with Playwright + Python + Pytest (sync API).

**Base URL:** `https://frontenddevh1.specigo.com/`

## Architecture

```
Tests  →  Flows  →  Pages (inherit BasePage)  →  Locators  →  Playwright
```

- **Pages** (`pages/`) — UI interaction layer, all inherit `BasePage`
- **Flows** (`flows/`) — Business logic orchestrators; return `{"completed": bool, "error_found": bool, "error_message": str|None}`
- **Tests** (`tests/`) — Thin; call flows, assert results
- **State** (`state/runtime_state.py`) — Shared session dict across flows (patient_id, samples, etc.)
- **Locators** (`locators/`) — CSS/XPath selectors by role
- **Test Data** (`test_data/`) — DDT JSON files per role

## Test Runner

```bash
# Standard (use venv pytest.exe — NOT system pytest)
.\Test\Scripts\pytest.exe <path> -v --tb=short

# Run by marker
.\Test\Scripts\pytest.exe -m e2e -v
.\Test\Scripts\pytest.exe -m smoke -v
.\Test\Scripts\pytest.exe -m regression -v

# Specific file
.\Test\Scripts\pytest.exe tests/e2e/acceptance/test_e2e_acceptance.py -v
```

## Test Structure

```
tests/
├── e2e/
│   ├── acceptance/     # Happy-path multi-phase flows
│   └── rejection/      # Rejection, recollection, rectification
└── regression/         # Role-wise regression (single role per file)

test_data/              # DDT JSON (1 file per role/scenario)
```

**Markers:** `smoke`, `regression`, `e2e`, `acceptance`, `rejection`, `labtech`, `doctor`

## Key Coding Patterns

### MNC Standard
All new code must have: type hints, docstrings, `BasePage` inheritance, section comments (`# --- Section ---`).

### AntD Quirks
- Overlays intercept clicks → use `el.evaluate("el => el.click()")` (JS dispatch)
- Combobox with pre-selected item → `click(force=True)`
- Dropdown salutations include dot (e.g. `Mr.`) → normalize in `select_salutation`
- Search combobox → use `type()` with `delay=80`, NOT `fill()`
- `#rc_select_N` IDs shift dynamically → always use label-based XPath, never ID-based

### General
- Scroll before interacting with below-fold elements
- Payment/number inputs → `type()`, not `fill()`
- `SEARCH_MOBILE_NTH = 3` on LabTech and Doctor pages (4 search fields exist, 0-indexed)
- Sample capture: `get_by_text("SampleName -", exact=True)` then `xpath=following::div[1]`
- Print Bill opens new tab → switch back with `page.context.pages[0].bring_to_front()`
- Sub-dept navigation: bidirectional Next/Prev loop, max 20 attempts

### DDT Pattern
```python
DATA = load_json(ROOT / "test_data/role/file.json")

def _entry(lst, key, val):
    return next(e for e in lst if e[key] == val)

# In test:
entry = _entry(DATA["patients"], "patient_id_ref", "P1")
result = execute_some_flow(page, entry)
assert result["completed"]
```

## Roles & E2E Flow

| Step | Role | Key Actions |
|------|------|-------------|
| 1 | Front Desk | Patient registration, test assignment, payment |
| 2 | Phlebotomist | Sample collection |
| 3 | Accession | Sample receipt & verification |
| 4 | Lab Technician | Results entry |
| 5 | Doctor | Approve / partial_approve / resample / retest / rectify |

**Doctor actions:** `approve`, `partial_approve`, `retest`, `resample`, `rectify`
- `approve`/`partial_approve`: fill params → save → Approve → dialog
- `rectify`: fill params → Rectify (no save) → dialog → reason → Submit → Yes

## Fixtures

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `browser_instance` | session | Chromium browser + context, records video |
| `page` | function | Fresh page per test, navigates to `/login` |
| `login_as(role)` | function | Login + auto-logout teardown |
| `*_data` fixtures | function | Load DDT JSON for each role |

## Artifacts & Reports

| Output | Path |
|--------|------|
| Failure screenshots | `artifacts/failures/` |
| Success screenshots | `artifacts/success/` |
| Traces (failures) | `artifacts/traces/` |
| Videos | `artifacts/videos/` |
| Pytest HTML | `reports/html/pytest_report.html` |
| Allure raw | `reports/allure-results/` |
| Summary HTML/JSON/CSV | `reports/summary_report.*` |
| Phase report | `reports/patient_phase_report.html` |

Generate Allure HTML: `allure generate reports/allure-results -o reports/allure-report --clean`

## Config

- `config/test_config.yaml` — timeout (30s), slow_mo (50ms), headless (false)
- `config/urls.yaml` — base_url
- `pytest.ini` — test discovery, markers, default `addopts`

## Known Bug Patterns

- **Relative form gating:** `is_existing and not is_new_relative` — see `feedback_relative_form_logic.md` in memory
- **AntD IDs shift** on Add Relative page — use label XPath always
- **`SEARCH_MOBILE_NTH = 3`** on pages with 4 search fields (LT, Doctor)

## Claude Session File — `.claude/test_run_session.json`

Maps every E2E test to its patient ID and scenario. **Read this before running or writing any E2E test.**

| Test | Patient | Scenario |
|------|---------|----------|
| `test_e2e_acceptance` | P1 | Full acceptance, 5 phases |
| `test_e2e_b4_add_relative_rectification` | P5 | Acceptance + add relative + doctor rectify |
| `test_e2e_b1_accession_rejection` | P2 | Accession rejects → reassign → recollect |
| `test_e2e_b2_labtech_rejection` | P3 | LT rejects → reassign → recollect |
| `test_e2e_b3_doctor_resample` | P1 | Doctor resamples → recollect |
| `test_e2e_bc_combined_rejection` | P1 | Combined accession + LT rejection |

**Rule:** Never write `pid = "P1"` (or any patient ID literal) inside a `.py` test file. Patient IDs live only in `.claude/test_run_session.json`. When adding a new test, add its entry there first.

## Reference
- `archive/` — Previous implementations; consult before writing new flows
- `memory/MEMORY.md` — Cross-session context (user prefs, patterns, project state)
