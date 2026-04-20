"""
UI error and popup detection for Playwright pages.

Scans for AntD error components, toasts, modals, alerts, and
generic validation messages without modifying page state.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


# ─────────────────────────────────────────────
# SELECTOR LIST
# Ordered by detection priority: most specific → most generic.
# ─────────────────────────────────────────────
_SELECTORS: list[str] = [
    # ── AntD message bar (top of screen) ─────────────────────────────────────
    ".ant-message-error",
    ".ant-message-warning",

    # ── AntD notification panel ───────────────────────────────────────────────
    ".ant-notification-notice-error .ant-notification-notice-description",
    ".ant-notification-notice-warning .ant-notification-notice-description",

    # ── AntD modal / confirm dialog ───────────────────────────────────────────
    ".ant-modal-confirm-body .ant-modal-confirm-content",
    ".ant-modal-body .ant-result-title",

    # ── AntD form validation text ─────────────────────────────────────────────
    ".ant-form-item-explain-error",

    # ── AntD alert bar ────────────────────────────────────────────────────────
    ".ant-alert-error .ant-alert-message",
    ".ant-alert-warning .ant-alert-message",

    # ── Generic ARIA / CSS patterns ───────────────────────────────────────────
    "[role='alert']",
    "[role='dialog'] .error",
    ".toast-error",
    ".error-message",
    ".validation-error",
    "[class*='error'][class*='message']",
    "[class*='alert'][class*='error']",
]

# Short timeout — must not slow down fast-passing tests
_TIMEOUT_MS: int = 300


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────
def detect_ui_errors(page: "Page") -> Optional[str]:
    """
    Scan the page for visible error or warning UI elements.

    Checks AntD message bars, notifications, modals, form validation,
    alert banners, and common CSS/ARIA patterns.

    Args:
        page: Active Playwright Page object.

    Returns:
        Text content of the first visible error element, or None if
        no errors are detected within the fast-check timeout.
    """
    for selector in _SELECTORS:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=_TIMEOUT_MS):
                text = el.inner_text(timeout=_TIMEOUT_MS)
                if text and text.strip():
                    return text.strip()
        except Exception:
            # Locator absent, timeout exceeded, page closed — skip silently
            continue
    return None
