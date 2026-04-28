# -*- coding: utf-8 -*-
"""
Shared helpers for embedding artifact assets into report HTML.

Used by:
    * `generators/stakeholder_html.py` — failure-block image embedding.
    * `generators/phase_html.py`       — inline failure screenshot + highlight
                                          overlay in patient_phase_report.html.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import List, Optional

from utils.failure_artifact import SIDECAR_SUFFIX


# =============================================================================
# IMAGE EMBEDDING
# =============================================================================
def embed_image(path_str: str) -> Optional[str]:
    """Read an image file and return a ``data:`` URL, or ``None`` if unreadable.

    Works on any path (absolute or workspace-relative). Empty string and
    missing files both return ``None`` so callers can fall back to a
    "no screenshot" placeholder.
    """
    if not path_str:
        return None
    try:
        p = Path(path_str)
        if not p.is_file():
            return None
        mime = mimetypes.guess_type(p.name)[0] or "image/png"
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"
    except (IOError, OSError):
        return None


# =============================================================================
# HIGHLIGHT METADATA
# =============================================================================
def load_highlights(screenshot_path: str) -> dict:
    """Return the sidecar highlight metadata for *screenshot_path*.

    Sidecar is expected at ``<screenshot_path>.json``. Missing or unreadable
    sidecars yield an empty payload — the renderer handles that gracefully
    by drawing the image without an overlay.

    Returns:
        ``{"page_size": {"width": int, "height": int},
           "highlights": [ {x, y, width, height, text, selector}, ... ] }``
    """
    empty = {"page_size": {"width": 0, "height": 0}, "highlights": []}
    if not screenshot_path:
        return empty
    sidecar = Path(str(screenshot_path) + SIDECAR_SUFFIX)
    if not sidecar.is_file():
        return empty
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (IOError, OSError, ValueError):
        return empty

    page_size = data.get("page_size") or {}
    highlights = data.get("highlights") or []
    if not isinstance(highlights, list):
        highlights = []
    return {
        "page_size": {
            "width": int(page_size.get("width") or 0),
            "height": int(page_size.get("height") or 0),
        },
        "highlights": [_clean_highlight(h) for h in highlights if isinstance(h, dict)],
    }


def _clean_highlight(h: dict) -> dict:
    """Coerce highlight dict fields to safe types for HTML rendering."""
    return {
        "x": float(h.get("x") or 0),
        "y": float(h.get("y") or 0),
        "width": float(h.get("width") or 0),
        "height": float(h.get("height") or 0),
        "text": str(h.get("text") or ""),
        "selector": str(h.get("selector") or ""),
    }


__all__: List[str] = ["embed_image", "load_highlights"]
