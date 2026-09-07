from __future__ import annotations

from typing import Any, Dict, Optional

from models.answer import AnswerPayload
from models.decision import ActionType
from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.daily_reminder_report import ReminderReport

from .base_intervention import BaseIntervention


class ReminiscenceIntervention(BaseIntervention):
    action_name = "reminiscence"

    def build_response(
        self,
        action: ActionType,
        protocol: Dict[str, Any],
        context: Dict[str, Any],
        transcript: Optional[TranscriptReport] = None,
        reminders: Optional[ReminderReport] = None,
    ) -> AnswerPayload:
        openings = protocol.get("opening_templates", [])
        opening = self._first(openings, "Would you like something familiar right now?")

        comfort_topics = context.get("comfort_topics") or []
        music_favorites = context.get("music_favorites") or []
        family_key_people = context.get("family_key_people") or []

        if music_favorites:
            text = f"{opening} Would you like to listen to something familiar, like {music_favorites[0]}?"
        elif comfort_topics:
            text = f"{opening} We could stay with something comforting, like {comfort_topics[0]}."
        elif family_key_people:
            name = family_key_people[0].get("name")
            if name:
                text = f"{opening} We could think about {name} for a gentle moment."
            else:
                text = opening
        else:
            text = opening

        return AnswerPayload(
            text_to_say=text,
            avatar_actions=["gentle_smile"],
            ui_actions=[],
            caregiver_alert_sent=False,
        )