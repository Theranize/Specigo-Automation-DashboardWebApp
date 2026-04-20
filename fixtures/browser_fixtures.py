"""Browser and page fixtures with full-screen (maximized) Chromium context."""

import pytest
from playwright.sync_api import sync_playwright
from utils.file_utils import load_yaml
from utils.reporting import VIDEOS_DIR

CONFIG_PATH = "config/test_config.yaml"
URLS_PATH   = "config/urls.yaml"


@pytest.fixture(scope="session")
def browser_instance(pytestconfig):
    """Launch Chromium maximized, yield browser/context/base_url dict."""
    config   = load_yaml(CONFIG_PATH)
    urls     = load_yaml(URLS_PATH)
    env      = pytestconfig.getoption("--env")   # "dev" | "staging"
    base_url = urls[env]["base_url"]
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=config.get("headless", False),
            slow_mo=config.get("slow_mo", 50),
            args=["--start-maximized"],
        )
        VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        context = browser.new_context(
            no_viewport=True,
            record_video_dir=str(VIDEOS_DIR),
            record_video_size={"width": 1920, "height": 1080},
        )
        context.set_default_timeout(config.get("timeout", 30000))
        context.base_url = base_url
        yield {"browser": browser, "context": context, "base_url": base_url}
        browser.close()


@pytest.fixture
def page(browser_instance):
    """Open a fresh page at /login; close after each test."""
    context = browser_instance["context"]
    pg = context.new_page()
    pg.goto(browser_instance["base_url"] + "login")
    yield pg
    pg.close()
