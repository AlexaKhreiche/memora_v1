from __future__ import annotations

from typing import Any, Dict, Optional

from models.answer import AnswerPayload
from models.decision import ActionType
from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.daily_reminder_report import ReminderReport

from .base_intervention import BaseIntervention


class FallIntervention(BaseIntervention):
    action_name = "fall_protocol"

    def build_response(
        self,
        action: ActionType,
        protocol: Dict[str, Any],
        context: Dict[str, Any],
        transcript: Optional[TranscriptReport] = None,
        reminders: Optional[ReminderReport] = None,
    ) -> AnswerPayload:
        openings = protocol.get("opening_templates", [])
        opening = self._first(
            openings,
            "I’m here with you. Please stay still. Help is being notified."
        )

        return AnswerPayload(
            text_to_say=opening,
            avatar_actions=["concerned_face"],
            ui_actions=[],
            caregiver_alert_sent=False,
        )