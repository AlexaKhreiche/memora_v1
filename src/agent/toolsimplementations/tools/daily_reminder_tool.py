from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from models.state import SessionState
from models.tools_schemas.daily_reminder_report import ReminderReport

from utils.patient_store import load_profile, load_daily_overrides, today_iso
from utils.schedule_utils import merge_effective_activities

# Dedup cache stored in-memory (MVP).
# Keyed by "patient_id::YYYY-MM-DD" -> set(notification_keys)
_NOTIFIED: dict[str, set[str]] = {}


def _parse_hhmm_today(hhmm: str) -> Optional[datetime]:
    """Parse HH:MM into a datetime for today (local time)."""
    try:
        now = datetime.now()
        h, m = hhmm.split(":")
        return now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except Exception:
        return None


def _priority_to_int(priority_raw: Any) -> int:
    """
    Your ReminderItem model expects an int.
    Support either:
      - int already (1/2/3)
      - strings "high"/"normal"/"low"
    Default: 2 (normal)
    """
    if isinstance(priority_raw, int):
        return priority_raw
    if isinstance(priority_raw, str):
        p = priority_raw.strip().lower()
        return {"high": 1, "urgent": 1, "normal": 2, "medium": 2, "low": 3}.get(p, 2)
    return 2


def _build_item(
    *,
    aid: str,
    title: str,
    dt: datetime,
    priority: int,
    instructions: Optional[str],
) -> Dict[str, Any]:
    """
    Build a ReminderItem-compatible dict.
    Keep fields aligned with your model:
      - required: id, title, due_iso
      - optional: priority, instructions
    """
    item: Dict[str, Any] = {
        "id": aid,
        "title": title,
        "due_iso": dt.isoformat(),
        "priority": priority,
        "instructions": instructions,
    }
    return item


def check_caregiver_schedule(state: SessionState) -> ReminderReport:
    """
    Reminder tool (caregiver-facing):
    - Loads profile routine + daily overrides for today
    - Computes effective activities
    - Returns ONLY reminders that are due *now*:
        * upcoming: within notify window
        * overdue: within grace..overdue_max window
    - Dedupes notifications in-memory to avoid repeated alerts in a single run
    - Computes next_reminder_iso (nearest future scheduled dt)
    """
    patient_id = state.patient_id
    day = today_iso()

    profile = load_profile(patient_id)
    daily = load_daily_overrides(patient_id, day)

    activities = merge_effective_activities(profile, daily)
    now = datetime.now()

    # In-memory dedupe (works for a long-running process)
    cache_key = f"{patient_id}::{day}"
    notified = _NOTIFIED.setdefault(cache_key, set())

    # Optional: allow daily file to track what caregiver marked completed
    completed_ids = set()
    if isinstance(daily, dict):
        completed = daily.get("completed")
        if isinstance(completed, list):
            completed_ids = {str(x).strip() for x in completed if str(x).strip()}

    due: List[Dict[str, Any]] = []
    next_dt: Optional[datetime] = None

    for a in activities:
        aid = str(a.get("id", "")).strip()
        title = str(a.get("title", "Activity")).strip()
        t = str(a.get("time", "")).strip()

        if not aid or not t:
            continue
        if aid in completed_ids:
            # caregiver has marked it done for today
            continue

        dt = _parse_hhmm_today(t)
        if dt is None:
            continue

        # Track next upcoming scheduled activity for UI
        if dt > now and (next_dt is None or dt < next_dt):
            next_dt = dt

        notify_before_min = int(a.get("notify_before_min", 15))
        grace_after_min = int(a.get("grace_after_min", 10))

        # Avoid end-of-day spam: only consider overdue for a bounded window
        overdue_max_min = int(a.get("overdue_max_min", 120))  # default 2h from scheduled time

        priority = _priority_to_int(a.get("priority", 2))
        instructions = a.get("instructions") or a.get("notes")

        # Windows
        upcoming_start = dt - timedelta(minutes=notify_before_min)
        upcoming_end = dt + timedelta(minutes=1)

        overdue_start = dt + timedelta(minutes=grace_after_min)
        overdue_end = dt + timedelta(minutes=overdue_max_min)

        base_key = f"{day}::{aid}::{t}"

        # Upcoming
        if upcoming_start <= now <= upcoming_end:
            key = base_key + "::upcoming"
            if key not in notified:
                due.append(
                    _build_item(
                        aid=aid,
                        title=title,
                        dt=dt,
                        priority=priority,
                        instructions=instructions,
                    )
                )
                notified.add(key)

        # Overdue (bounded)
        if overdue_start <= now <= overdue_end:
            key = base_key + "::overdue"
            if key not in notified:
                due.append(
                    _build_item(
                        aid=aid,
                        title=title,
                        dt=dt,
                        priority=priority,
                        instructions=instructions,
                    )
                )
                notified.add(key)

    return ReminderReport(
        reminders_due=due,
        next_reminder_iso=(next_dt.isoformat() if next_dt else None),
    )