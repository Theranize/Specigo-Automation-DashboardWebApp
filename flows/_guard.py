"""
Mid-flow UI error guard.

Single helper that every flow file imports. Wraps the comprehensive
``utils.error_detector.detect_ui_errors`` scan and populates the flow's
result dict in the common shape every flow already uses
(``error_found`` / ``error_message`` / ``completed``).

Usage pattern in flow code:

    from flows._guard import check_ui_error
    ...
    pp.click_search()
    if check_ui_error(page, result, "post-search"):
        return result

If ``detect_ui_errors`` finds a visible AntD message / notification /
modal / form-validation / alert / ARIA error, the helper writes the
error text into ``result["error_message"]`` (prefixed with the
``context`` label) and returns True so the caller short-circuits.

Expected-error semantics (P7 limit, P11 duplicate-mobile):
    Pass ``expected_err={"should_appear": True, "message": "<substr>"}``
    and the helper sets ``result["expected_error_matched"] = True`` when
    the visible text contains the configured substring — same contract
    as ``flows.front_desk_flow._set_error``.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from utils.error_detector import detect_ui_errors


# =============================================================================
# PUBLIC API
# =============================================================================
def check_ui_error(
    page: Any,
    result: Dict[str, Any],
    context: str,
    expected_err: Optional[Dict[str, Any]] = None,
) -> bool:
    """Return True (and fill *result*) if a UI error is visible on *page*.

    Args:
        page:         Active Playwright Page.
        result:       Flow result dict — ``error_found`` / ``error_message`` /
                      ``completed`` are written on a hit. ``expected_error_matched``
                      is also set when applicable.
        context:      Short label describing where the check fired
                      (e.g. ``"post-search"``). Prefixes the captured error
                      text so the test report says where it tripped.
        expected_err: Optional DDT entry of the form
                      ``{"should_appear": True, "message": "<substr>"}``.
                      When present and the visible text contains the
                      configured substring, ``expected_error_matched`` is
                      set so the caller (e.g. P7 / P11 tests) can treat
                      the run as a pass-with-warning.

    Returns:
        True  → caller should ``return result`` immediately.
        False → no error visible, continue.
    """
    err = detect_ui_errors(page)
    if err is None:
        return False

    result["error_found"]   = True
    result["error_message"] = f"{context}: {err.text}"
    result["completed"]     = False

    if expected_err and expected_err.get("should_appear"):
        if expected_err.get("message", "") in err.text:
            result["expected_error_matched"] = True

    return True


__all__ = ["check_ui_error"]
