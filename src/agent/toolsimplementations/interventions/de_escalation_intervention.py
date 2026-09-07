from __future__ import annotations

from typing import Any, Dict, Optional

from models.answer import AnswerPayload
from models.decision import ActionType
from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.daily_reminder_report import ReminderReport

from .base_intervention import BaseIntervention


class DeEscalationIntervention(BaseIntervention):
    action_name = "de_escalation"

    def build_response(
        self,
        action: ActionType,
        protocol: Dict[str, Any],
        context: Dict[str, Any],
        transcript: Optional[TranscriptReport] = None,
        reminders: Optional[ReminderReport] = None,
    ) -> AnswerPayload:
        openings = protocol.get("opening_templates", [])
        grounding_templates = protocol.get("grounding_templates", [])

        opening = self._first(openings, "You’re safe. I’m here with you.")
        grounding = self._first(grounding_templates, "We can take this slowly.")

        comfort_topics = context.get("comfort_topics") or []
        music_favorites = context.get("music_favorites") or []

        parts = [opening]

        if grounding not in parts:
            parts.append(grounding)

        if music_favorites:
            parts.append(
                f"Would it help to stay with something familiar, like {music_favorites[0]}?"
            )
        elif comfort_topics:
            parts.append(
                f"Would it help to stay with something familiar, like {comfort_topics[0]}?"
            )

        text = " ".join(parts).strip()

        return AnswerPayload(
            text_to_say=text,
            avatar_actions=["calm_voice"],
            ui_actions=[],
            caregiver_alert_sent=False,
        )