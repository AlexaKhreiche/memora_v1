# common base schema for all tools

from __future__ import annotations

from enum import Enum


class EmotionLabel(str, Enum):
    calm = "calm"
    happy = "happy"
    sad = "sad"
    confused = "confused"
    agitated = "agitated"
    distressed = "distressed"
    anxious = "anxious"
    neutral = "neutral"

    # Keep for backward compatibility (if anything uses it)
    angry = "angry"

    uncertain = "uncertain"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"