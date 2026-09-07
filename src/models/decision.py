from __future__ import annotations

from enum import Enum
from typing import Dict, Any
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    # patient-facing interaction modes
    conversation = "CONVERSATION"
    de_escalation = "DE_ESCALATION"
    reminiscence = "REMINISCENCE"
    fall_protocol = "FALL_PROTOCOL"

    # caregiver-facing alerts
    caregiver_reminder_alert = "CAREGIVER_REMINDER_ALERT"
    wandering_alert = "WANDERING_ALERT"

    # meta/system
    ask_to_repeat = "ASK_TO_REPEAT"


class Decision(BaseModel):
    action: ActionType
    reason: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    override: bool = False