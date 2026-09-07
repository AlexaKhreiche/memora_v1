from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import time

from agent.perception.vision.fall_detector import PoseKeypoint


@dataclass
class PresenceConfig:
    absence_threshold_s: float = 8.0      # seconds with no person before alerting
    visibility_min: float = 0.30           # min keypoint visibility to count
    min_visible_keypoints: int = 3         # need at least this many visible keypoints
    confidence_ramp_s: float = 15.0        # seconds over which confidence ramps to 1.0


@dataclass
class PresenceResult:
    person_present: bool
    wandering_detected: bool
    confidence: float
    absence_duration_s: float
    reasons: List[str]


DEFAULT_PRESENCE_CONFIG = PresenceConfig()


class PresenceDetector:
    """
    Tracks whether a person is visible in the camera frame.
    If they disappear for longer than absence_threshold_s,
    flags wandering_detected = True.
    """

    def __init__(self, config: PresenceConfig = DEFAULT_PRESENCE_CONFIG) -> None:
        self.cfg = config
        self._last_seen_ts: Optional[float] = None   # last time person was visible
        self._absence_start_ts: Optional[float] = None  # when person first disappeared

    def _count_visible(self, keypoints: Dict[str, PoseKeypoint]) -> int:
        return sum(
            1 for kp in keypoints.values()
            if kp.visibility >= self.cfg.visibility_min
        )

    def update(self, keypoints: Optional[Dict[str, PoseKeypoint]]) -> PresenceResult:
        now = time.time()

        # Determine if a person is present in this frame
        person_present = False
        if keypoints is not None:
            visible_count = self._count_visible(keypoints)
            person_present = visible_count >= self.cfg.min_visible_keypoints

        if person_present:
            # Person is here — reset absence tracking
            self._last_seen_ts = now
            self._absence_start_ts = None
            return PresenceResult(
                person_present=True,
                wandering_detected=False,
                confidence=0.0,
                absence_duration_s=0.0,
                reasons=[],
            )

        # --- Person is NOT visible ---

        # First frame with no person (or system just started)
        if self._absence_start_ts is None:
            self._absence_start_ts = now

        absence_s = now - self._absence_start_ts
        reasons: List[str] = []

        if keypoints is None:
            reasons.append("No pose detected")
        else:
            reasons.append(f"Too few visible keypoints ({self._count_visible(keypoints)})")

        # Not long enough to trigger yet
        if absence_s < self.cfg.absence_threshold_s:
            reasons.append(f"Absent {absence_s:.1f}s (threshold {self.cfg.absence_threshold_s:.0f}s)")
            return PresenceResult(
                person_present=False,
                wandering_detected=False,
                confidence=0.0,
                absence_duration_s=absence_s,
                reasons=reasons,
            )

        # Threshold exceeded — wandering detected
        # Confidence ramps from 0.70 at threshold to 1.0 over confidence_ramp_s
        extra_s = absence_s - self.cfg.absence_threshold_s
        ramp = min(extra_s / max(self.cfg.confidence_ramp_s, 0.1), 1.0)
        confidence = 0.70 + 0.30 * ramp

        reasons.append(f"Absent {absence_s:.1f}s — exceeded threshold")

        return PresenceResult(
            person_present=False,
            wandering_detected=True,
            confidence=confidence,
            absence_duration_s=absence_s,
            reasons=reasons,
        )
