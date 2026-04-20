"""Date filter resolution utility — global config with per-patient override."""

from pathlib import Path
from utils.file_utils import load_yaml

_ROOT = Path(__file__).resolve().parents[1]
_CFG = load_yaml(_ROOT / "config/test_config.yaml")


def resolve_filters(patient_entry: dict) -> dict:
    """Return patient-level filters if present, else fall back to global config.

    Global date is set once in config/test_config.yaml under the ``filters`` key.
    To override for a specific patient, add a ``filters`` key to that DDT entry::

        {"patient_id_ref": "P15", "filters": {"from_date": "14/04/2026", "to_date": "14/04/2026"}, ...}

    All other patients with no ``filters`` key inherit the global date automatically.
    """
    return patient_entry.get("filters") or _CFG["filters"]
