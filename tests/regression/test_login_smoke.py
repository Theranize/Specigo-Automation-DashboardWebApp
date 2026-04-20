from pathlib import Path

import pytest
from utils.file_utils import load_json

_ROOT = Path(__file__).resolve().parents[2]
LOGIN_DATA = load_json(_ROOT / "test_data/login/login_ddt.json")
ALL_ROLES = list(LOGIN_DATA.keys())


@pytest.mark.smoke
@pytest.mark.parametrize("role", ALL_ROLES)
def test_login_logout(page, login_as, role):
    login_as(role)
    assert "login" not in page.url, f"{role}: should have navigated away from login page"
