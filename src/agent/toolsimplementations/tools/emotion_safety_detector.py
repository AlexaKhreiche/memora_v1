from __future__ import annotations

from typing import Dict, List, Tuple

from models.shared import EmotionLabel, RiskLevel
from models.tools_schemas.emotion_safety_detector_report import SignalReport


# DeepFace expressions mapped to the application's existing categories.
# Surprise has no positive/negative valence, so do not infer confusion from it.
EMOTION_MAPPING = {
    "happy": EmotionLabel.happy,
    "sad": EmotionLabel.sad,
    "angry": EmotionLabel.agitated,
    "disgust": EmotionLabel.agitated,
    "fear": EmotionLabel.distressed,
    "neutral": EmotionLabel.neutral,
    "surprise": EmotionLabel.uncertain,
}


def _aggregate_emotions(face_scores: Dict[str, float]) -> List[Tuple[EmotionLabel, float]]:
    # Preserve the strongest expression's score; do not boost confidence.
    buckets: Dict[EmotionLabel, float] = {}
    for name, score in face_scores.items():
        label = EMOTION_MAPPING.get(name)
        if label is not None:
            buckets[label] = max(buckets.get(label, 0.0), float(score))
    return sorted(buckets.items(), key=lambda item: item[1], reverse=True)


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
    """Face-only emotion mapping using DeepFace scores."""

    def build_report(
        self,
        face_raw_scores: Dict[str, float],
    ) -> Tuple[SignalReport, Dict]:
        aggregated = _aggregate_emotions(face_raw_scores or {})
        debug = {
            "source": "face",
            "mapped_count": len(aggregated),
            "top5": aggregated[:5],
        }

        if not aggregated:
            # No observation must not masquerade as a neutral expression.
            label = EmotionLabel.uncertain
            conf = 0.0
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