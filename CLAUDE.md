# Playwright Automation — CLAUDE.md

**Canonical docs live in `docs/`. Read these first:**

1. **`docs/PROJECT.md`** — architecture, directory map, DDT pattern, patient map (P1–P14), run scheme, markers, coding standards, known quirks.
2. **`docs/SESSIONS.md`** — dated, newest-first log of what changed in each session and why.

Also useful:
- `.claude/test_run_session.json` — test → patient mapping. Never hardcode patient IDs (`pid = "P1"`) in `.py` files; tests must read from this file.
- `archive/` — previous implementations; consult before writing new flows.
- `memory/MEMORY.md` — cross-session memory index (if present).

**Base URL:** `https://frontenddevh1.specigo.com/`  •  **Runner:** `.\Test\Scripts\pytest.exe <path> -v`  •  **Markers:** `smoke`, `regression`, `e2e`, `acceptance`, `rejection`, `rectification`, `labtech`, `doctor`
