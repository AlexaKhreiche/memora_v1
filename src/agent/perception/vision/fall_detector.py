from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time
import math


# Same concept as TS PoseKeypoint
@dataclass
class PoseKeypoint:
    name: str
    x: float
    y: float
    visibility: float


@dataclass
class FallResult:
    fall_detected: bool
    confidence: float
    reasons: List[str]


@dataclass
class FallDetectionConfig:
    torso_angle_threshold: float = 45.0
    ground_level_threshold: float = 0.65
    head_hip_diff_threshold: float = 0.15

    vertical_drop_threshold: float = 0.12
    velocity_threshold: float = 0.08

    motionless_threshold_ms: int = 1500
    overall_confidence_threshold: float = 0.45

    visibility_min: float = 0.30


DEFAULT_CONFIG = FallDetectionConfig()


def _angle_deg(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    rad = math.atan2(dy, dx)
    return abs(rad * (180.0 / math.pi))


def _mid(p1: Tuple[float, float], p2: Tuple[float, float]) -> Tuple[float, float]:
    return ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)


class FallDetector:
    """
    Port of your TS scoring method:
    - torso horizontal
    - body low in frame
    - head-hip alignment
    - sudden vertical drop + sustained downward velocity
    - legs horizontal
    - motionless after indicators
    """

    def __init__(self, config: FallDetectionConfig = DEFAULT_CONFIG) -> None:
        self.cfg = config
        self.pose_history: List[Dict[str, PoseKeypoint]] = []
        self.velocity_history: List[float] = []
        self.last_movement_time_ms: int = int(time.time() * 1000)

    def _get(self, kps: Dict[str, PoseKeypoint], name: str) -> Optional[PoseKeypoint]:
        kp = kps.get(name)
        if kp is None:
            return None
        return kp if kp.visibility >= self.cfg.visibility_min else None

    def _core_body_y(self, kps: Dict[str, PoseKeypoint]) -> Optional[float]:
        pts = [
            self._get(kps, "left_hip"),
            self._get(kps, "right_hip"),
            self._get(kps, "left_shoulder"),
            self._get(kps, "right_shoulder"),
        ]
        pts = [p for p in pts if p is not None]
        if len(pts) < 2:
            return None
        return sum(p.y for p in pts) / len(pts)

    def update(self, keypoints: Optional[Dict[str, PoseKeypoint]]) -> FallResult:
        if keypoints is None:
            # no pose => no decision here (your later “disappearance fall” can go here if you want)
            return FallResult(False, 0.0, ["no_pose"])

        cfg = self.cfg
        confidence = 0.0
        reasons: List[str] = []

        ls = self._get(keypoints, "left_shoulder")
        rs = self._get(keypoints, "right_shoulder")
        lh = self._get(keypoints, "left_hip")
        rh = self._get(keypoints, "right_hip")
        nose = self._get(keypoints, "nose")
        la = self._get(keypoints, "left_ankle")
        ra = self._get(keypoints, "right_ankle")

        # ===========================================
        # FACTOR 1: TORSO ANGLE
        # ===========================================
        if ls and rs and lh and rh:
            shoulder_mid = _mid((ls.x, ls.y), (rs.x, rs.y))
            hip_mid = _mid((lh.x, lh.y), (rh.x, rh.y))
            torso_angle = _angle_deg(shoulder_mid, hip_mid)

            angle_from_horizontal = min(torso_angle, 180.0 - torso_angle)
            if angle_from_horizontal < cfg.torso_angle_threshold:
                factor = 1.0 - (angle_from_horizontal / cfg.torso_angle_threshold)
                confidence += 0.35 * factor
                reasons.append(f"Torso horizontal ({angle_from_horizontal:.0f}°)")

        # ===========================================
        # FACTOR 2: GROUND LEVEL (hips low)
        # ===========================================
        if lh and rh:
            hip_mid = _mid((lh.x, lh.y), (rh.x, rh.y))
            if hip_mid[1] > cfg.ground_level_threshold:
                factor = (hip_mid[1] - cfg.ground_level_threshold) / (1.0 - cfg.ground_level_threshold)
                confidence += 0.25 * min(factor, 1.0)
                reasons.append(f"Body low ({hip_mid[1]*100:.0f}%)")

        # ===========================================
        # FACTOR 3: HEAD-HIP ALIGNMENT
        # ===========================================
        if nose and (lh or rh):
            hip = lh if lh else rh
            if hip:
                y_diff = abs(nose.y - hip.y)
                if y_diff < cfg.head_hip_diff_threshold:
                    factor = 1.0 - (y_diff / cfg.head_hip_diff_threshold)
                    confidence += 0.20 * factor
                    reasons.append("Head level with hips")

                if nose.y > hip.y + 0.05:
                    confidence += 0.15
                    reasons.append("Head below hips")

        # ===========================================
        # FACTOR 4: SUDDEN VERTICAL DROP + VELOCITY
        # ===========================================
        if len(self.pose_history) >= 3:
            current_core_y = self._core_body_y(keypoints)
            prev_core_y = self._core_body_y(self.pose_history[-3])

            if current_core_y is not None and prev_core_y is not None:
                drop = current_core_y - prev_core_y  # positive = moving down

                if drop > cfg.vertical_drop_threshold:
                    confidence += 0.25
                    reasons.append("Rapid downward movement")

                self.velocity_history.append(drop)
                if len(self.velocity_history) > 10:
                    self.velocity_history.pop(0)

                avg_vel = sum(self.velocity_history) / len(self.velocity_history)
                if avg_vel > cfg.velocity_threshold:
                    confidence += 0.10
                    reasons.append("Sustained downward motion")

        # ===========================================
        # FACTOR 5: LEGS HORIZONTAL
        # ===========================================
        ankle = la if la else ra
        hip = lh if lh else rh
        if ankle and hip:
            diff = abs(ankle.y - hip.y)
            if diff < 0.20:
                confidence += 0.10
                reasons.append("Legs horizontal")

        # ===========================================
        # FACTOR 6: MOTIONLESS AFTER INDICATORS
        # ===========================================
        now_ms = int(time.time() * 1000)
        time_since_movement = now_ms - self.last_movement_time_ms
        if confidence > 0.20 and time_since_movement > cfg.motionless_threshold_ms:
            confidence += 0.15
            reasons.append(f"Motionless {time_since_movement/1000:.1f}s")

        # Movement detection (reset motionless timer)
        if len(self.pose_history) > 0:
            last_pose = self.pose_history[-1]
            total = 0.0
            count = 0

            for name, kp in keypoints.items():
                if kp.visibility < cfg.visibility_min:
                    continue
                last_kp = last_pose.get(name)
                if last_kp and last_kp.visibility >= cfg.visibility_min:
                    dx = kp.x - last_kp.x
                    dy = kp.y - last_kp.y
                    total += math.sqrt(dx * dx + dy * dy)
                    count += 1

            avg_movement = (total / count) if count > 0 else 0.0
            if avg_movement > 0.015:
                self.last_movement_time_ms = now_ms

        confidence = min(confidence, 1.0)
        detected = confidence >= cfg.overall_confidence_threshold

        # Keep history
        self.pose_history.append(keypoints)
        if len(self.pose_history) > 60:
            self.pose_history.pop(0)

        return FallResult(detected, confidence, reasons)
