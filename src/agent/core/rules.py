from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from models.state import SessionState
from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.emotion_safety_detector_report import SignalReport
from models.tools_schemas.daily_reminder_report import ReminderReport
from models.decision import Decision, ActionType


class EventType(str, Enum):
    SYSTEM_START = "SYSTEM_START"
    PATIENT_MESSAGE = "PATIENT_MESSAGE"
    SENSOR_ALERT = "SENSOR_ALERT"
    TIMER_TICK = "TIMER_TICK"
    EMOTION_UPDATE = "EMOTION_UPDATE"


class Event(BaseModel):
    type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)


def _seconds_since(iso_ts: Optional[str]) -> float:
    if not iso_ts:
        return 0.0
    try:
        ts = datetime.fromisoformat(iso_ts)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return 0.0


def _emotion_to_mode(label: str) -> str:
    label = (label or "").strip().lower()

    if label in {"angry", "distressed", "agitated", "anxious"}:
        return "de_escalation"

    if label in {"sad", "neutral", "calm"}:
        return "reminiscence"

    if label in {"happy", "confused", "uncertain"}:
        return "conversation"

    return "conversation"


def choose_decision(
    state: SessionState,
    transcript: Optional[TranscriptReport],
    signals: Optional[SignalReport],
    reminders: Optional[ReminderReport],
) -> Decision:
    # 1) Safety overrides are immediate.
    if signals is not None:
        fall_conf = float(getattr(signals, "fall_confidence", 0.0))
        wandering_conf = float(getattr(signals, "wandering_confidence", 0.0))

        if bool(getattr(signals, "fall_detected", False)) and fall_conf >= 0.45:
            return Decision(
                action=ActionType.fall_protocol,
                reason="Fall detected by vision",
                override=True,
                confidence=fall_conf,
            )

        if bool(getattr(signals, "wandering_detected", False)) and wandering_conf >= 0.70:
            return Decision(
                action=ActionType.wandering_alert,
                reason="Wandering detected by vision",
                override=True,
                confidence=wandering_conf,
            )

    # 2) Caregiver reminders are immediate.
    if reminders is not None and len(getattr(reminders, "reminders_due", [])) > 0:
        return Decision(
            action=ActionType.caregiver_reminder_alert,
            reason="Caregiver reminder due",
            confidence=1.0,
        )

    # 3) Emotional intervention uses stabilized face-emotion label mapped to mode.
    stable_label = (state.stable_emotion_label or "").strip().lower()
    stable_mode = _emotion_to_mode(stable_label)
    stable_conf = float(getattr(state, "stable_emotion_confidence", 0.0))
    stable_seconds = _seconds_since(getattr(state, "stable_emotion_since_iso", None))

    if stable_mode == "de_escalation" and stable_conf >= 0.40 and stable_seconds >= 0.50:
        return Decision(
            action=ActionType.de_escalation,
            reason=(
                f"Stable emotion label={stable_label} mapped to mode={stable_mode} "
                f"(conf={stable_conf:.2f}, {stable_seconds:.1f}s)"
            ),
            confidence=stable_conf,
        )

    if stable_mode == "reminiscence" and stable_conf >= 0.60 and stable_seconds >= 5.0:
        return Decision(
            action=ActionType.reminiscence,
            reason=(
                f"Stable emotion label={stable_label} mapped to mode={stable_mode} "
                f"(conf={stable_conf:.2f}, {stable_seconds:.1f}s)"
            ),
            confidence=stable_conf,
        )

    if stable_mode == "conversation" and stable_conf >= 0.50:
        return Decision(
            action=ActionType.conversation,
            reason=(
                f"Stable emotion label={stable_label} mapped to mode={stable_mode} "
                f"(conf={stable_conf:.2f}, {stable_seconds:.1f}s)"
            ),
            confidence=stable_conf,
        )

    # 4) Default
    return Decision(
        action=ActionType.conversation,
        reason="Default conversation",
        confidence=1.0,
    )