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

    # ── AntD form validation text — try the most-specific class first, then
    #    fall back to broader patterns so we catch every AntD version (4.x
    #    nests an "-error" inner div under .ant-form-item-explain; 5.x can
    #    use the explain-error class directly; some themes use "-validating"
    #    or alert role only). Field-validation is the most common mid-flow
    #    error, so we err on the side of broader matching here.
    ".ant-form-item-explain-error",
    ".ant-form-item-has-error .ant-form-item-explain",
    ".ant-form-item-has-error [role='alert']",
    "[class*='form-item-explain-error']",
    "[class*='form-item-has-error'] [class*='form-item-explain']",

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

    **Success / info filtering:** A few of our selectors (notably
    ``[role='alert']``) match success / info banners as well as errors
    because AntD reuses the role for accessibility announcements. After
    every match we walk the ancestor chain looking for class fragments
    like ``message-success``, ``alert-info``, ``notice-success`` etc., and
    skip those — otherwise P7's "Mobile number found" success toast would
    register as an error and short-circuit the post-search step.

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
            if _is_inside_non_error(el):
                continue
            text = (el.inner_text(timeout=_TIMEOUT_MS) or "").strip()
            if not text:
                continue
            box = _full_page_box(page, el)
            return UiError(text=text, selector=selector, box=box)
        except Exception:
            # Locator absent, timeout exceeded, page closed — skip silently
            continue

    # Last-resort generic fallback: scan for any visible element whose visible
    # text starts with a common red-validation prefix used by Specigo's AntD
    # theme. These messages render through a class structure that does not
    # match any standard AntD selector (e.g. wrapped in a ``<p>`` with a
    # bespoke ``.text-error`` class), so the structured selectors above can
    # miss them. We bias toward correctness here: a missed mid-flow error
    # cascades into multiple downstream phase failures, while a false hit
    # only fails fast on a real visible message.
    try:
        candidate = page.evaluate(
            """() => {
                const PATTERNS = [
                    /^Please (enter|select|provide) /i,
                    /^Please choose /i,
                    /should contain only /i,
                    /is required\\b/i,
                    /^Invalid /i,
                    /^Enter (a |an )?valid /i,
                    /already (registered|exists|in use)/i,
                    /not\\s+found\\b/i,
                    /limit (has been )?reached/i,
                    /found with the given /i,
                ];
                const NON_ERROR_RE = /(message-success|message-info|notice-success|notice-info|alert-success|alert-info|toast-success|toast-info|\\bsuccess\\b|\\binfo\\b)/i;
                function inSuccessAncestor(el) {
                    let cur = el;
                    while (cur && cur.tagName !== 'BODY') {
                        const cls = (cur.className && typeof cur.className === 'string') ? cur.className : '';
                        if (NON_ERROR_RE.test(cls)) return true;
                        cur = cur.parentElement;
                    }
                    return false;
                }
                const all = document.querySelectorAll('body *');
                for (const el of all) {
                    const txt = (el.innerText || '').trim();
                    if (!txt || txt.length > 240) continue;
                    if (el.children && el.children.length > 0) continue;  // leaf only
                    const r = el.getBoundingClientRect();
                    if (r.width <= 0 || r.height <= 0) continue;
                    const cs = window.getComputedStyle(el);
                    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
                    if (parseFloat(cs.opacity || '1') < 0.1) continue;
                    if (inSuccessAncestor(el)) continue;
                    for (const pat of PATTERNS) {
                        if (pat.test(txt)) {
                            return {
                                text: txt,
                                selector: 'fallback:text-pattern',
                                box: {x: r.left + window.pageXOffset,
                                      y: r.top + window.pageYOffset,
                                      width: r.width, height: r.height},
                            };
                        }
                    }
                }
                return null;
            }"""
        )
        if candidate and candidate.get("text"):
            return UiError(
                text=candidate["text"],
                selector=candidate.get("selector", "fallback:text-pattern"),
                box=candidate.get("box"),
            )
    except Exception:
        pass

    return None


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────
def _is_inside_non_error(locator) -> bool:
    """Return True if the matched element is actually inside a success/info container.

    AntD reuses ``[role='alert']`` and similar generic classes for success
    and info announcements (e.g. "Mobile number found" toast on the Front
    Desk search results). Without this filter, those would register as
    errors and short-circuit the flow before the *real* error appears.

    Walks the ancestor chain up to ``<body>`` looking for class fragments
    that indicate a non-error message: ``message-success``,
    ``notice-success``, ``alert-info``, etc. Errors silently treat as
    non-success (fail-open) so genuine errors never get suppressed.
    """
    try:
        return bool(locator.evaluate(
            """el => {
                const NON_ERROR_RE = /(message-success|message-info|notice-success|notice-info|alert-success|alert-info|toast-success|toast-info|\\bsuccess\\b|\\binfo\\b)/i;
                let cur = el;
                while (cur && cur.tagName !== 'BODY') {
                    const cls = (cur.className && typeof cur.className === 'string') ? cur.className : '';
                    if (NON_ERROR_RE.test(cls)) return true;
                    cur = cur.parentElement;
                }
                return false;
            }""",
            timeout=_TIMEOUT_MS,
        ))
    except Exception:
        return False


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
