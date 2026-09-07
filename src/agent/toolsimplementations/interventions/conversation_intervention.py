from __future__ import annotations

from typing import Any, Dict, Optional

from models.answer import AnswerPayload
from models.decision import ActionType
from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.daily_reminder_report import ReminderReport

from .base_intervention import BaseIntervention


class ConversationIntervention(BaseIntervention):
    action_name = "conversation"

    def build_response(
        self,
        action: ActionType,
        protocol: Dict[str, Any],
        context: Dict[str, Any],
        transcript: Optional[TranscriptReport] = None,
        reminders: Optional[ReminderReport] = None,
    ) -> AnswerPayload:
        openings = protocol.get("opening_templates", [])
        opening = self._first(openings, "I’m here with you.")

        patient_name = context.get("patient_name") or ""
        user_text = (transcript.transcript if transcript else "").strip()

        if not user_text:
            if patient_name:
                text = f"{opening} How are you feeling, {patient_name}?"
            else:
                text = f"{opening} How are you feeling?"
        else:
            text = opening

        return AnswerPayload(
            text_to_say=text,
            avatar_actions=["listening_pose"],
            ui_actions=[],
            caregiver_alert_sent=False,
        )