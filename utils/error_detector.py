"""
UI error and popup detection for Playwright pages.

Scans for AntD error components, toasts, modals, alerts, and
generic validation messages without modifying page state.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


# ─────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────
@dataclass
class UiError:
    """One detected UI error: its visible text, the selector that matched, and its bounding box (if available).

    `box` carries the element rect in CSS pixels relative to the *full page*
    (viewport `bounding_box()` plus current scroll offset), so it lines up
    with `page.screenshot(full_page=True)` output. May be ``None`` when
    Playwright cannot resolve a box (detached element, zero-area, etc.).
    """
    text: str
    selector: str
    box: Optional[dict] = None  # {"x": float, "y": float, "width": float, "height": float}


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
def detect_ui_errors(page: "Page") -> Optional[UiError]:
    """Scan the page for the first visible error / warning UI element.

    Checks AntD message bars, notifications, modals, form validation,
    alert banners, and common CSS / ARIA patterns. Captures the element's
    bounding box (translated to full-page coordinates) so the reporting
    layer can highlight it on the failure screenshot.

    Args:
        page: Active Playwright Page object.

    Returns:
        UiError with text + selector + box, or None if nothing detected
        within the fast-check timeout.
    """
    for selector in _SELECTORS:
        try:
            el = page.locator(selector).first
            if not el.is_visible(timeout=_TIMEOUT_MS):
                continue
            text = (el.inner_text(timeout=_TIMEOUT_MS) or "").strip()
            if not text:
                continue
            box = _full_page_box(page, el)
            return UiError(text=text, selector=selector, box=box)
        except Exception:
            # Locator absent, timeout exceeded, page closed — skip silently
            continue
    return None


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────
def _full_page_box(page: "Page", locator) -> Optional[dict]:
    """Return the locator's bounding box in full-page coordinates.

    Playwright's `bounding_box()` is viewport-relative; for a `full_page=True`
    screenshot we need to add the current scroll offset so the rectangle
    lines up with pixels in the saved PNG.
    """
    try:
        box = locator.bounding_box(timeout=_TIMEOUT_MS)
        if not box:
            return None
        scroll = page.evaluate(
            "() => ({x: window.pageXOffset || 0, y: window.pageYOffset || 0})"
        )
        return {
            "x": float(box["x"]) + float(scroll.get("x", 0) or 0),
            "y": float(box["y"]) + float(scroll.get("y", 0) or 0),
            "width": float(box["width"]),
            "height": float(box["height"]),
        }
    except Exception:
        return None
