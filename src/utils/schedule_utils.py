from __future__ import annotations

from typing import Any, Dict, List


def _index_by_id(activities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for a in activities:
        aid = str(a.get("id", "")).strip()
        if aid:
            out[aid] = a
    return out


def merge_effective_activities(profile: Dict[str, Any], daily: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Returns today's effective activities list:
    - Start from profile.routine_template.activities
    - Apply daily.overrides.remove (by id)
    - Apply daily.overrides.update (partial patches by id)
    - Apply daily.overrides.add (append)
    """
    base = (
        (profile.get("routine_template") or {}).get("activities")
        or []
    )

    # Copy base so we don't mutate loaded dicts
    activities: List[Dict[str, Any]] = [dict(a) for a in base]

    overrides = (daily.get("overrides") or {})
    remove_ids = set(str(x).strip() for x in (overrides.get("remove") or []) if str(x).strip())

    # remove
    if remove_ids:
        activities = [a for a in activities if str(a.get("id", "")).strip() not in remove_ids]

    # update
    updates = overrides.get("update") or []
    if updates:
        by_id = _index_by_id(activities)
        for patch in updates:
            pid = str(patch.get("id", "")).strip()
            if not pid or pid not in by_id:
                continue
            # Merge patch fields (except id)
            for k, v in patch.items():
                if k == "id":
                    continue
                by_id[pid][k] = v

        # rebuild list preserving original order
        activities = list(by_id.values())

    # add
    adds = overrides.get("add") or []
    for a in adds:
        if isinstance(a, dict):
            activities.append(dict(a))

    return activities