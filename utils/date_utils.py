"""Date filter resolution utility — global config with per-patient override."""

from pathlib import Path
from utils.file_utils import load_yaml

_ROOT = Path(__file__).resolve().parents[1]
_CFG = load_yaml(_ROOT / "config/test_config.yaml")
_LOCAL_GROUPS = _CFG.get("local_filters") or []

# Flatten every group's (patients, dates) into a {pid: {from_date, to_date}}
# index at module load. A pid that appears in multiple groups uses the LAST
# group's dates (last-write-wins) — surface that as a config error at review
# time; the lookup itself stays O(1).
_LOCAL_INDEX = {
    pid: {"from_date": group["from_date"], "to_date": group["to_date"]}
    for group in _LOCAL_GROUPS
    for pid in (group.get("patients") or [])
}


def resolve_filters(patient_entry: dict) -> dict:
    """Three-tier resolution for date filters.

    1. Per-entry ``"filters"`` key on the DDT entry (highest priority).
    2. Centralized ``local_filters`` in config/test_config.yaml, when the
       entry's ``patient_id_ref`` appears in any group's ``patients`` list.
    3. Global ``filters`` in config/test_config.yaml (fallback).

    The ``local_filters`` block is a list of override groups. Each group
    pairs one date with one or more patient IDs, so the same schema covers
    shared dates (one group, many pids), independent dates (many groups,
    one pid each), and any mix of the two::

        local_filters:
          - patients: ["P13", "P15"]   # share 17/04
            from_date: "17/04/2026"
            to_date:   "17/04/2026"
          - patients: ["P14"]          # owns 20/04
            from_date: "20/04/2026"
            to_date:   "20/04/2026"
    """
    if patient_entry.get("filters"):
        return patient_entry["filters"]
    pid = patient_entry.get("patient_id_ref")
    if pid and pid in _LOCAL_INDEX:
        return _LOCAL_INDEX[pid]
    return _CFG["filters"]
