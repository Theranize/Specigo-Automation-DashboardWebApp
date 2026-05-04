"""Login/logout fixture with runtime state tracking per role."""

import pytest
from datetime import datetime
from utils.file_utils import load_json
from flows.login_flow import execute_login
from flows.logout_flow import execute_logout
from state import runtime_state

LOGIN_DATA_PATH = "test_data/login/login_ddt.json"


@pytest.fixture
def login_as(page, pytestconfig):
    """Yield a callable that logs in as the given role; logs out and clears state on teardown."""
    credentials_data = load_json(LOGIN_DATA_PATH)
    env = pytestconfig.getoption("--env")
    env_creds = credentials_data[env]
    logged_in = False

    def do_login(role: str) -> None:
        nonlocal logged_in
        creds = env_creds[role]
        execute_login(page, role, creds)
        runtime_state.set_value("current_role", role)
        runtime_state.set_value("username", creds["username"])
        runtime_state.set_value("login_timestamp", datetime.now().isoformat())
        logged_in = True

    yield do_login

    if logged_in:
        try:
            execute_logout(page)
        except Exception:
            pass
    runtime_state.clear()


@pytest.fixture
def swap_user(page, pytestconfig):
    """Mid-test login swap primitive for super-user (admin/manager) runs.

    Yields a callable `_swap(page, role)` that:
      - Logs out the current role (best-effort) and navigates back to /login.
      - Logs in as the requested role using env-appropriate credentials.
      - Updates runtime_state (current_role, username, login_timestamp).
      - Is idempotent on first call (no logout when no prior role).

    Teardown logs out the final role and clears runtime_state, so this fixture
    is self-contained and does not depend on `login_as`.
    """
    credentials_data = load_json(LOGIN_DATA_PATH)
    env = pytestconfig.getoption("--env")
    env_creds = credentials_data[env]
    state = {"current_role": None}

    def _swap(_page, role: str) -> None:
        if state["current_role"] is not None:
            try:
                execute_logout(_page)
            except Exception:
                pass
            try:
                _page.wait_for_load_state("networkidle")
                _page.goto(_page.context.base_url + "login")
                _page.wait_for_load_state("networkidle")
            except Exception:
                pass
        creds = env_creds[role]
        execute_login(_page, role, creds)
        runtime_state.set_value("current_role", role)
        runtime_state.set_value("username", creds["username"])
        runtime_state.set_value("login_timestamp", datetime.now().isoformat())
        state["current_role"] = role

    yield _swap

    if state["current_role"] is not None:
        try:
            execute_logout(page)
        except Exception:
            pass
    runtime_state.clear()
