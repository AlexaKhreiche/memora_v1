from __future__ import annotations

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from ..shared import EmotionLabel, RiskLevel


class SignalReport(BaseModel):
    # Multimodal emotion (final fused result)
    emotion_label: EmotionLabel = EmotionLabel.uncertain
    emotion_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Computer vision / sensors (final booleans + confidence)
    fall_detected: bool = False
    fall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    wandering_detected: bool = False
    wandering_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Optional continuous risk score used by thresholds/rules
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_level: RiskLevel = RiskLevel.low


