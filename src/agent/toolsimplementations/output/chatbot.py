from __future__ import annotations

from typing import Optional

from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.emotion_safety_detector_report import SignalReport
from models.tools_schemas.daily_reminder_report import ReminderReport
from models.decision import ActionType


def generate_patient_text(
    mode: ActionType,
    transcript: Optional[TranscriptReport],
    signals: Optional[SignalReport],
    reminders: Optional[ReminderReport],
) -> str:
    # Later: load YAML mode + prompt + call LLM.
    if mode == ActionType.ask_to_repeat:
        return "Sorry, I didn’t catch that. Could you repeat it?"

    if mode == ActionType.reminiscence:
        return "That’s lovely. Can you tell me about a happy memory from when you were younger?"

    if mode == ActionType.validation:
        return "That sounds really hard. I’m here with you. What’s making you feel this way right now?"

    if mode == ActionType.reminder_delivery:
        due = (reminders.reminders_due if reminders else [])
        if not due:
            return "You’re all set for now."
        first = due[0]
        return f"Reminder: {first.title}. {first.instructions or ''}".strip()

    # default chat
    user_text = (transcript.transcript if transcript else "").strip()
    if not user_text:
        return "How are you feeling right now?"
    return f"I hear you. Tell me a bit more about that."
