# -*- coding: utf-8 -*-
"""
Sidecar writer for failure-screenshot highlight metadata.

Given a freshly captured `full_page=True` screenshot, persist a small JSON
file alongside it describing the page size and any detected UI-error
bounding boxes. The reporting layer (patient_phase_report.html) reads this
sidecar to render a CSS-overlay rectangle on top of the embedded image,
pointing the reader at the failure region.

File layout:
    artifacts/failures/p2-…-acceptissue1.png
    artifacts/failures/p2-…-acceptissue1.png.json   <- sidecar

Sidecar schema:
    {
        "page_size": {"width": <int>, "height": <int>},
        "highlights": [
            {
                "x": float, "y": float, "width": float, "height": float,
                "text": "<error message>",
                "selector": "<css/xpath that matched>"
            },
            ...
        ]
    }

Empty `highlights` is valid — it means a screenshot was taken but no UI
error was detected. The report falls back to "embedded image, no overlay".

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from utils.error_detector import detect_ui_errors

if TYPE_CHECKING:
    from playwright.sync_api import Page


# =============================================================================
# CONSTANTS
# =============================================================================
SIDECAR_SUFFIX = ".json"  # sidecar = "<screenshot>.png.json"


# =============================================================================
# PUBLIC API
# =============================================================================
def write_highlight_sidecar(
    page: "Page",
    screenshot_path: str,
) -> Optional[str]:
    """Write the highlight-metadata sidecar next to *screenshot_path*.

    Best-effort — never raises. On any failure (closed page, evaluate
    error, write error) returns ``None`` and the report falls back to the
    plain embedded image.

    Args:
        page:           Active Playwright Page (still alive).
        screenshot_path: Absolute or workspace-relative path to the just-saved
                         screenshot PNG.

    Returns:
        The sidecar path as a string on success, otherwise ``None``.
    """
    if not screenshot_path or screenshot_path == "---":
        return None

    try:
        page_size = _page_size(page)
        ui_err = detect_ui_errors(page)
        highlights = []
        if ui_err and ui_err.box:
            highlights.append({
                "x": float(ui_err.box["x"]),
                "y": float(ui_err.box["y"]),
                "width": float(ui_err.box["width"]),
                "height": float(ui_err.box["height"]),
                "text": ui_err.text,
                "selector": ui_err.selector,
            })

        payload = {
            "page_size": page_size,
            "highlights": highlights,
        }

        sidecar = Path(str(screenshot_path) + SIDECAR_SUFFIX)
        sidecar.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(sidecar)
    except Exception:
        return None


# =============================================================================
# INTERNAL HELPERS
# =============================================================================
def _page_size(page: "Page") -> dict:
    """Return the document's full scroll size in CSS pixels.

    Falls back to ``{"width": 0, "height": 0}`` if the evaluate call fails;
    the renderer treats unknown sizes by skipping the aspect-ratio hint.
    """
    try:
        size = page.evaluate(
            "() => ({"
            "  width: document.documentElement.scrollWidth,"
            "  height: document.documentElement.scrollHeight"
            "})"
        )
        return {
            "width": int(size.get("width") or 0),
            "height": int(size.get("height") or 0),
        }
    except Exception:
        return {"width": 0, "height": 0}
