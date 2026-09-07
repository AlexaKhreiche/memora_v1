from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.emotion_safety_detector_report import SignalReport
from models.tools_schemas.daily_reminder_report import ReminderReport
from models.decision import Decision


class SessionState(BaseModel):
    patient_id: str

    phase: str = "IDLE"
    turn_index: int = 0

    last_transcript: Optional[TranscriptReport] = None
    last_signals: Optional[SignalReport] = None
    last_reminders: Optional[ReminderReport] = None
    last_decision: Optional[Decision] = None
    last_output_text: str = ""

    fall_active: bool = False
    wandering_active: bool = False
    fall_active_since_iso: Optional[str] = None
    wandering_active_since_iso: Optional[str] = None
    last_fall_alert_iso: Optional[str] = None
    last_wandering_alert_iso: Optional[str] = None

    # Rolling face-emotion history for stabilization
    emotion_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Stabilized emotion mode used by the brain
    stable_emotion_label: Optional[str] = None
    stable_emotion_confidence: float = 0.0
    stable_emotion_since_iso: Optional[str] = None

    # Prevents rapid oscillation between patient-facing interventions
    active_intervention: Optional[str] = None
    active_intervention_since_iso: Optional[str] = None
    
    last_ui_payload: Dict[str, Any] = {}

    # Short-term conversation history for LLM context (last N turns)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)

    # Inactivity tracking
    last_patient_message_iso: Optional[str] = None

    # Lightweight conversation state
    last_detected_intent: Optional[str] = None
    current_topic: Optional[str] = None
    recent_topics: List[str] = Field(default_factory=list)
    turns_since_avatar_question: int = 0

    #caregiver ui 
    caregiver_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    safety_log: List[Dict[str, Any]] = Field(default_factory=list)
    live_emotion_log: List[Dict[str, Any]] = Field(default_factory=list)