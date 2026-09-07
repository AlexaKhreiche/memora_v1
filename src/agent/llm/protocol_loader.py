from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _protocol_dir() -> Path:
    return (
        _project_root()
        / "src"
        / "agent"
        / "toolsimplementations"
        / "interventions"
        / "interaction_protocols"
    )


def load_protocol(protocol_name: str) -> dict[str, Any]:
    protocol_path = _protocol_dir() / f"{protocol_name}.yaml"

    if not protocol_path.exists():
        raise FileNotFoundError(f"Protocol not found: {protocol_path}")

    with protocol_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return data