import json
import yaml
from pathlib import Path


def load_json(path):
    with open(Path(path), "r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path):
    with open(Path(path), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
