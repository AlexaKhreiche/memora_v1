from __future__ import annotations

import json
from pathlib import Path
from datetime import date
from typing import Any, Dict, Optional

DATA_ROOT = Path("data") / "patients"


def _patient_dir(patient_id: str) -> Path:
    return DATA_ROOT / patient_id


def profile_path(patient_id: str) -> Path:
    return _patient_dir(patient_id) / "profile.json"


def daily_path(patient_id: str, day: str) -> Path:
    # day = "YYYY-MM-DD"
    return _patient_dir(patient_id) / "daily" / f"{day}.json"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_profile(patient_id: str) -> Dict[str, Any]:
    return load_json(profile_path(patient_id))


def load_daily_overrides(patient_id: str, day: str) -> Dict[str, Any]:
    return load_json(daily_path(patient_id, day))


def today_iso() -> str:
    return date.today().isoformat()

def save_profile(patient_id: str, data: Dict[str, Any]) -> None:
    save_json(profile_path(patient_id), data)


def save_daily_overrides(patient_id: str, day: str, data: Dict[str, Any]) -> None:
    save_json(daily_path(patient_id, day), data)