"""
Standalone Fall Detector Test
==============================
Run from the project root:
    python test_fall_detector.py

Window shows:
  - Live camera feed with pose skeleton
  - Risk badge: LOW RISK / HIGH RISK / FALL DETECTED
  - Confidence bar
  - Real-time log of active detection reasons

Press Q to quit.
"""
from __future__ import annotations

import sys
import time
import cv2
import mediapipe as mp
import numpy as np

# Allow running from project root without installing the package
sys.path.insert(0, "src")

from agent.perception.vision.pose_tracker import PoseTracker
from agent.perception.vision.fall_detector import FallDetector

# ── Risk level thresholds (mirrors FallDetectionConfig) ──────────────────────
CONF_LOW  = 0.25   # below → Low Risk
CONF_HIGH = 0.45   # above → Fall Detected  (overall_confidence_threshold)

# ── Colours (BGR) ─────────────────────────────────────────────────────────────
GREEN  = (60, 200, 60)
YELLOW = (0, 200, 255)
RED    = (40, 40, 220)
WHITE  = (255, 255, 255)
BLACK  = (0, 0, 0)
DARK   = (30, 30, 30)

MP_POSE = mp.solutions.pose
MP_DRAW = mp.solutions.drawing_utils
MP_STYLE = mp.solutions.drawing_styles


def risk_label_and_color(confidence: float, fall_detected: bool):
    if fall_detected:
        return "FALL DETECTED", RED
    if confidence >= CONF_LOW:
        return "HIGH RISK", YELLOW
    return "LOW RISK", GREEN


def draw_badge(frame, label: str, color, confidence: float):
    h, w = frame.shape[:2]

    # ── Semi-transparent top banner ───────────────────────────────────────────
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 90), DARK, -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    # ── Risk label ────────────────────────────────────────────────────────────
    font = cv2.FONT_HERSHEY_DUPLEX
    cv2.putText(frame, label, (20, 58), font, 1.6, color, 3, cv2.LINE_AA)

    # ── Confidence bar ────────────────────────────────────────────────────────
    bar_x, bar_y, bar_w, bar_h = w - 260, 18, 220, 22
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), -1)
    fill = int(bar_w * min(confidence, 1.0))
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), color, -1)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), WHITE, 1)

    # threshold tick at CONF_HIGH
    tick_x = bar_x + int(bar_w * CONF_HIGH)
    cv2.line(frame, (tick_x, bar_y - 3), (tick_x, bar_y + bar_h + 3), WHITE, 2)

    cv2.putText(frame, f"conf: {confidence:.2f}", (bar_x, bar_y + bar_h + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, WHITE, 1, cv2.LINE_AA)


def draw_log_panel(frame, reasons: list[str], log_lines: list[str]):
    """Bottom panel with active reasons + rolling log."""
    h, w = frame.shape[:2]
    panel_h = 120
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - panel_h), (w, h), DARK, -1)
    cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

    font = cv2.FONT_HERSHEY_SIMPLEX

    # Active factors header
    cv2.putText(frame, "Active factors:", (12, h - panel_h + 20),
                font, 0.50, (180, 180, 180), 1, cv2.LINE_AA)
    active_text = "  " + ("  |  ".join(reasons) if reasons else "none")
    cv2.putText(frame, active_text, (12, h - panel_h + 40),
                font, 0.48, WHITE, 1, cv2.LINE_AA)

    # Rolling log
    cv2.putText(frame, "Log:", (12, h - panel_h + 65),
                font, 0.50, (180, 180, 180), 1, cv2.LINE_AA)
    for i, line in enumerate(log_lines[-3:]):   # show last 3 lines
        cv2.putText(frame, line, (12, h - panel_h + 82 + i * 16),
                    font, 0.44, (200, 230, 200), 1, cv2.LINE_AA)


def draw_skeleton(frame, mp_result):
    """Draw MediaPipe pose skeleton directly on frame."""
    if mp_result and mp_result.pose_landmarks:
        MP_DRAW.draw_landmarks(
            frame,
            mp_result.pose_landmarks,
            MP_POSE.POSE_CONNECTIONS,
            landmark_drawing_spec=MP_DRAW.DrawingSpec(color=(0, 255, 180), thickness=2, circle_radius=3),
            connection_drawing_spec=MP_DRAW.DrawingSpec(color=(255, 255, 255), thickness=2),
        )


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open camera.")
        sys.exit(1)

    tracker  = PoseTracker()
    detector = FallDetector()

    # MediaPipe pose instance for skeleton drawing (reuse inside PoseTracker would require
    # exposing the raw result, so we run a lightweight second pass just for drawing)
    mp_pose_draw = MP_POSE.Pose(
        static_image_mode=False,
        model_complexity=0,          # fastest, only for drawing
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    log_lines: list[str] = []
    last_fall_log = 0.0

    print("Fall Detector Test running — press Q in the window to quit.\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        frame = cv2.flip(frame, 1)   # mirror so it feels natural

        # ── Pose skeleton (raw MediaPipe pass) ────────────────────────────────
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_result = mp_pose_draw.process(rgb)
        draw_skeleton(frame, mp_result)

        # ── Fall detection ────────────────────────────────────────────────────
        kps    = tracker.extract_keypoints(frame)
        result = detector.update(kps)

        label, color = risk_label_and_color(result.confidence, result.fall_detected)

        # ── Overlays ─────────────────────────────────────────────────────────
        draw_badge(frame, label, color, result.confidence)

        # Rolling log entries
        now = time.time()
        if result.fall_detected and now - last_fall_log > 1.0:
            last_fall_log = now
            ts = time.strftime("%H:%M:%S")
            log_lines.append(f"[{ts}] FALL DETECTED  conf={result.confidence:.2f}  {result.reasons}")

        draw_log_panel(frame, result.reasons, log_lines)

        cv2.imshow("Fall Detector Test  [Q = quit]", frame)

        # ── Terminal output (throttled) ───────────────────────────────────────
        if result.fall_detected and now - last_fall_log < 0.05:
            print(f"[FALL] conf={result.confidence:.2f}  {result.reasons}")

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
