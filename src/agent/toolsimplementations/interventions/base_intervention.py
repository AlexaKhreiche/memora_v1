from __future__ import annotations

from typing import Any, Dict, Optional

from models.answer import AnswerPayload
from models.decision import ActionType
from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.daily_reminder_report import ReminderReport


class BaseIntervention:
    action_name: str = "base"

    def build_response(
        self,
        action: ActionType,
        protocol: Dict[str, Any],
        context: Dict[str, Any],
        transcript: Optional[TranscriptReport] = None,
        reminders: Optional[ReminderReport] = None,
    ) -> AnswerPayload:
        raise NotImplementedError("Intervention must implement build_response()")

    def _first(self, items: list[str], default: str) -> str:
        return items[0] if items else default