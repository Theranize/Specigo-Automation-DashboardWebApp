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
