# -*- coding: utf-8 -*-
"""
Display-formatting helpers shared across reporting generators.

Currently provides duration formatting that adapts the unit to the
magnitude of the value: seconds for short runs, minutes for medium,
hours for long. Keeps the report tables compact and readable without
forcing the reader to mentally divide by 60 / 3600.

MNC standard: type hints, docstrings, section comments.
"""
from __future__ import annotations


# =============================================================================
# DURATION
# =============================================================================
def fmt_duration(seconds: float) -> str:
    """Format a duration in seconds as ``Xs`` / ``Xm Ys`` / ``Xh Ym Zs``.

    Tier breakpoints:
        * ``< 60s``       → ``"12.3s"`` (one decimal, trailing unit)
        * ``< 3600s``     → ``"5m 23s"`` (seconds zero-padded to 2 digits)
        * ``>= 3600s``    → ``"1h 02m 05s"`` (minutes/seconds zero-padded)

    Non-numeric / negative inputs return ``"-"`` so callers can drop the
    helper into a template without pre-validating.
    """
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "-"
    if s < 0:
        return "-"

    if s < 60:
        return f"{s:.1f}s"

    total_s = int(round(s))
    if total_s < 3600:
        m, rem = divmod(total_s, 60)
        return f"{m}m {rem:02d}s"

    h, rest = divmod(total_s, 3600)
    m, rem  = divmod(rest, 60)
    return f"{h}h {m:02d}m {rem:02d}s"


__all__ = ["fmt_duration"]
