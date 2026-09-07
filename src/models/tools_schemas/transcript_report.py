#transcript reporter tool schema
#produced by: conversation_listener.py 
#used by: Emotion detection + Brain

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class TranscriptReport(BaseModel):
    #transcript = the text version of the patient's response 
    transcript: str = Field(default="", description="Best-effort text transcript.")
    #confidence = how sure we are that the speech was correctly transcribed, between 0 and 1
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    #language = language detection
    language: Optional[str] = Field(default=None, description="e.g., 'en', 'ar'")
