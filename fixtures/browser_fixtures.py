"""Browser and page fixtures with full-screen (maximized) Chromium context."""

import pytest
from playwright.sync_api import sync_playwright
from utils.file_utils import load_yaml
from utils.reporting import VIDEOS_DIR

CONFIG_PATH = "config/test_config.yaml"
URLS_PATH   = "config/urls.yaml"


@pytest.fixture
def browser_instance(pytestconfig):
    """Launch Chromium per test; yield browser/context/base_url; close on teardown.

    Function-scoped so each test gets its own browser window. The post-test
    visual hold and logout-on-fail are handled in the autouse
    ``_trace_and_timing`` teardown in ``conftest.py``, which runs before this
    fixture tears down.
    """
    config   = load_yaml(CONFIG_PATH)
    urls     = load_yaml(URLS_PATH)
    env      = pytestconfig.getoption("--env")   # "dev" | "staging"
    base_url = urls[env]["base_url"]
    headless = config.get("headless", False)
    with sync_playwright() as p:
        # In headed mode --start-maximized stretches Chromium to the screen
        # so the page renders at full resolution. In headless that arg is a
        # no-op and Chromium falls back to its default 800x600 viewport, which
        # crops AntD modals/sidebars and breaks layout-sensitive locators.
        # Force an explicit 1920x1080 window+viewport when headless.
        launch_args = (
            ["--window-size=1920,1080"] if headless else ["--start-maximized"]
        )
        browser = p.chromium.launch(
            headless=headless,
            slow_mo=config.get("slow_mo", 50),
            args=launch_args,
        )
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        context_kwargs: dict = {
            "record_video_dir": str(VIDEOS_DIR),
            "record_video_size": {"width": 1920, "height": 1080},
        }
        if headless:
            context_kwargs["viewport"] = {"width": 1920, "height": 1080}
        else:
            context_kwargs["no_viewport"] = True
        context = browser.new_context(**context_kwargs)
        context.set_default_timeout(config.get("timeout", 30000))
        context.base_url = base_url
        try:
            yield {"browser": browser, "context": context, "base_url": base_url}
        finally:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


@pytest.fixture
def page(browser_instance):
    """Open a fresh page at /login; close after each test."""
    context = browser_instance["context"]
    pg = context.new_page()
    pg.goto(browser_instance["base_url"] + "login")
    yield pg
    pg.close()
