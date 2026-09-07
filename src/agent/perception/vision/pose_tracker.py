from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import cv2
import mediapipe as mp


@dataclass
class PoseKeypoint:
    name: str
    x: float  # normalized 0..1
    y: float  # normalized 0..1
    visibility: float


class PoseTracker:
    """
    MediaPipe pose tracker (mediapipe==0.10.21).
    Exposes extract_keypoints(frame) used by the TS-style fall scoring.
    """

    def __init__(self) -> None:
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def extract_keypoints(self, frame_bgr) -> Optional[Dict[str, PoseKeypoint]]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self.pose.process(frame_rgb)

        if not result.pose_landmarks:
            return None

        lm = result.pose_landmarks.landmark

        def kp(idx: int, name: str) -> PoseKeypoint:
            return PoseKeypoint(
                name=name,
                x=float(lm[idx].x),
                y=float(lm[idx].y),
                visibility=float(getattr(lm[idx], "visibility", 1.0)),
            )

        return {
            "nose": kp(self.mp_pose.PoseLandmark.NOSE.value, "nose"),
            "left_shoulder": kp(self.mp_pose.PoseLandmark.LEFT_SHOULDER.value, "left_shoulder"),
            "right_shoulder": kp(self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value, "right_shoulder"),
            "left_hip": kp(self.mp_pose.PoseLandmark.LEFT_HIP.value, "left_hip"),
            "right_hip": kp(self.mp_pose.PoseLandmark.RIGHT_HIP.value, "right_hip"),
            "left_ankle": kp(self.mp_pose.PoseLandmark.LEFT_ANKLE.value, "left_ankle"),
            "right_ankle": kp(self.mp_pose.PoseLandmark.RIGHT_ANKLE.value, "right_ankle"),
        }

    # Optional alias (if any older code calls extract())
    def extract(self, frame_bgr):
        return self.extract_keypoints(frame_bgr)
