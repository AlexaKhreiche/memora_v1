from __future__ import annotations
from typing import Any, Dict

from utils.patient_store import load_daily_overrides, save_daily_overrides, today_iso


def mark_activity_completed(patient_id: str, activity_id: str, day: str | None = None) -> Dict[str, Any]:
    day = day or today_iso()

    daily = load_daily_overrides(patient_id, day)
    if not daily:
        daily = {
            "schema_version": "1.0",
            "patient_id": patient_id,
            "date": day,
            "overrides": {"add": [], "update": [], "remove": []},
            "completed": [],
        }

    completed = daily.get("completed")
    if not isinstance(completed, list):
        completed = []

    if activity_id not in completed:
        completed.append(activity_id)

    daily["completed"] = completed
    save_daily_overrides(patient_id, day, daily)
    return daily