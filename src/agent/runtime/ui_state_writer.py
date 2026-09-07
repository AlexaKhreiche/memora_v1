from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _data_dir() -> Path:
    data_dir = _project_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def write_ui_payload(payload: dict[str, Any]) -> None:
    output_path = _data_dir() / "latest_ui_payload.json"
    tmp_path = output_path.with_suffix(".tmp")

    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Atomic rename — prevents the frontend from reading a partial file
    tmp_path.replace(output_path)