from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models.shared import EmotionLabel, RiskLevel
from models.tools_schemas.emotion_safety_detector_report import SignalReport


# -----------------------------
# Ported from ADRD_System:
# src/app/api/emotion-face/route.ts
# -----------------------------
EMOTION_MAPPING: Dict[str, EmotionLabel] = {
    # Calm/Relaxed
    "Calmness": EmotionLabel.calm,
    "Contentment": EmotionLabel.calm,
    "Relief": EmotionLabel.calm,
    "Serenity": EmotionLabel.calm,
    "Satisfaction": EmotionLabel.calm,

    # Happy
    "Joy": EmotionLabel.happy,
    "Amusement": EmotionLabel.happy,
    "Ecstasy": EmotionLabel.happy,
    "Excitement": EmotionLabel.happy,
    "Triumph": EmotionLabel.happy,
    "Pride": EmotionLabel.happy,
    "Interest": EmotionLabel.happy,
    "Enthusiasm": EmotionLabel.happy,

    # Sad
    "Sadness": EmotionLabel.sad,
    "Disappointment": EmotionLabel.sad,
    "Grief": EmotionLabel.sad,
    "Despair": EmotionLabel.sad,
    "Nostalgia": EmotionLabel.sad,

    # Confused
    "Confusion": EmotionLabel.confused,
    "Doubt": EmotionLabel.confused,
    "Contemplation": EmotionLabel.confused,
    "Surprise (negative)": EmotionLabel.confused,

    # Agitated
    "Anger": EmotionLabel.agitated,
    "Annoyance": EmotionLabel.agitated,
    "Frustration": EmotionLabel.agitated,
    "Contempt": EmotionLabel.agitated,
    "Disgust": EmotionLabel.agitated,
    "Irritation": EmotionLabel.agitated,

    # Distressed
    "Distress": EmotionLabel.distressed,
    "Fear": EmotionLabel.distressed,
    "Anxiety": EmotionLabel.distressed,  # ADRD_System maps Anxiety into distressed bucket
    "Horror": EmotionLabel.distressed,
    "Pain": EmotionLabel.distressed,
    "Panic": EmotionLabel.distressed,
    "Terror": EmotionLabel.distressed,

    # Anxious
    "Awkwardness": EmotionLabel.anxious,
    "Embarrassment": EmotionLabel.anxious,
    "Nervousness": EmotionLabel.anxious,
    "Tension": EmotionLabel.anxious,
    "Worry": EmotionLabel.anxious,
    "Shame": EmotionLabel.anxious,

    # Neutral
    "Boredom": EmotionLabel.neutral,
    "Concentration": EmotionLabel.neutral,
    "Realization": EmotionLabel.neutral,
    "Determination": EmotionLabel.neutral,
}


def _aggregate_hume_emotions(face_scores: Dict[str, float]) -> List[Tuple[EmotionLabel, float]]:
    """
    Port of ADRD_System aggregateEmotions():
      - group Hume emotions by mapped category
      - average within category
      - boost avg slightly (x1.2) and cap at 1.0
      - return sorted desc
    """
    buckets: Dict[EmotionLabel, List[float]] = {
        EmotionLabel.calm: [],
        EmotionLabel.happy: [],
        EmotionLabel.sad: [],
        EmotionLabel.confused: [],
        EmotionLabel.agitated: [],
        EmotionLabel.distressed: [],
        EmotionLabel.anxious: [],
        EmotionLabel.neutral: [],
    }

    for name, score in (face_scores or {}).items():
        mapped = EMOTION_MAPPING.get(name)
        if mapped is not None:
            buckets[mapped].append(float(score))

    result: List[Tuple[EmotionLabel, float]] = []
    for label, scores in buckets.items():
        if scores:
            avg = sum(scores) / len(scores)
            boosted = min(1.0, avg * 1.2)
            result.append((label, boosted))

    result.sort(key=lambda x: x[1], reverse=True)
    return result


def _risk_from_emotion(label: EmotionLabel, conf: float) -> Tuple[float, RiskLevel]:
    """
    Simple risk mapping:
      - distressed: highest
      - agitated/anxious: high
      - confused/sad: medium
      - neutral/calm/happy: low
    """
    conf = max(0.0, min(1.0, float(conf)))

    if label == EmotionLabel.distressed:
        score = 0.65 + 0.35 * conf
    elif label in (EmotionLabel.agitated, EmotionLabel.anxious):
        score = 0.45 + 0.35 * conf
    elif label in (EmotionLabel.confused, EmotionLabel.sad):
        score = 0.30 + 0.30 * conf
    else:
        score = 0.05 + 0.20 * conf

    score = max(0.0, min(1.0, score))

    if score < 0.30:
        level = RiskLevel.low
    elif score < 0.60:
        level = RiskLevel.medium
    elif score < 0.80:
        level = RiskLevel.high
    else:
        level = RiskLevel.critical

    return score, level


class EmotionSafetyDetector:
    """Face-only emotion mapping using Hume AI scores."""

    def build_report(
        self,
        face_raw_scores: Dict[str, float],
    ) -> Tuple[SignalReport, Dict]:
        aggregated = _aggregate_hume_emotions(face_raw_scores or {})
        debug = {
            "source": "face",
            "mapped_count": len(aggregated),
            "top5": aggregated[:5],
        }

        if not aggregated:
            # Mirror your previous behavior: default neutral when nothing detected
            label = EmotionLabel.neutral
            conf = 0.5
        else:
            label, conf = aggregated[0]

        risk_score, risk_level = _risk_from_emotion(label, conf)

        report = SignalReport(
            emotion_label=label,
            emotion_confidence=float(conf),
            risk_score=float(risk_score),
            risk_level=risk_level,
        )
        return report, debug