from __future__ import annotations

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AnswerPayload(BaseModel):
    text_to_say: str = Field(default="")
    avatar_actions: List[str] = Field(default_factory=list)
    ui_actions: List[Dict[str, Any]] = Field(default_factory=list)
    tts_audio_ref: Optional[str] = None

    caregiver_alert_sent: bool = False

    response_language: Optional[str] = None
    interaction_mode: Optional[str] = None
    speech_style: Optional[Dict[str, Any]] = None