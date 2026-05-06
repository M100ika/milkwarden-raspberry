import yaml
from pathlib import Path

_DEFAULT = Path(__file__).parent.parent / "config" / "edge.yaml"


def load(path: Path = _DEFAULT) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)
