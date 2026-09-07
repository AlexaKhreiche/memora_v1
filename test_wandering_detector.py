"""
Standalone Wandering Detector Test
====================================
Run from the project root:
    python test_wandering_detector.py

Window shows:
  - Live camera feed
  - PERSON IN FRAME      (green)  — person visible
  - HIGH RISK: WANDERING (yellow) — absent 1–8 s
  - CRITICAL: WANDERING  (red)    — absent > 8 s + message sent
  - Absence timer bar
  - Real-time log panel

Press Q to quit.
"""
from __future__ import annotations

import sys
import time
import cv2
import mediapipe as mp
import numpy as np

sys.path.insert(0, "src")

from agent.perception.vision.pose_tracker import PoseTracker
from agent.perception.vision.presence_detector import PresenceDetector

# ── Thresholds ────────────────────────────────────────────────────────────────
HIGH_RISK_START_S = 1.0   # absent > 1s  → High Risk
CRITICAL_S        = 8.0   # absent > 8s  → Critical

# ── Colours (BGR) ─────────────────────────────────────────────────────────────
GREEN  = (60, 200, 60)
YELLOW = (0, 200, 255)
RED    = (40, 40, 220)
WHITE  = (255, 255, 255)
DARK   = (30, 30, 30)

MP_POSE = mp.solutions.pose
MP_DRAW = mp.solutions.drawing_utils


def status_from_result(absence_s: float, person_present: bool, wandering: bool):
    if person_present:
        return "PERSON IN FRAME", GREEN, False
    if absence_s >= CRITICAL_S or wandering:
        return "CRITICAL: WANDERING DETECTED", RED, True
    if absence_s >= HIGH_RISK_START_S:
        return "HIGH RISK: WANDERING", YELLOW, False
    return "PERSON IN FRAME", GREEN, False   # just left frame, not long enough yet


def draw_banner(frame, label: str, color, absence_s: float, critical: bool):
    h, w = frame.shape[:2]

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 100), DARK, -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    # Main label
    font = cv2.FONT_HERSHEY_DUPLEX
    cv2.putText(frame, label, (20, 58), font, 1.1, color, 3, cv2.LINE_AA)

    # Absence timer
    if absence_s > 0:
        timer_text = f"Out of frame: {absence_s:.1f}s"
        cv2.putText(frame, timer_text, (20, 88), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, WHITE, 1, cv2.LINE_AA)

    # Absence bar (0 → CRITICAL_S)
    bar_x, bar_y, bar_w, bar_h = w - 270, 18, 230, 22
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), -1)
    fill = int(bar_w * min(absence_s / CRITICAL_S, 1.0))
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill, bar_y + bar_h), color, -1)
    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), WHITE, 1)

    # Tick at HIGH_RISK_START_S
    tick_x = bar_x + int(bar_w * (HIGH_RISK_START_S / CRITICAL_S))
    cv2.line(frame, (tick_x, bar_y - 3), (tick_x, bar_y + bar_h + 3), YELLOW, 2)

    cv2.putText(frame, f"0s", (bar_x, bar_y + bar_h + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)
    cv2.putText(frame, f"{CRITICAL_S:.0f}s", (bar_x + bar_w - 18, bar_y + bar_h + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)

    # Flashing "MESSAGE SENT" tag on critical
    if critical and int(time.time() * 2) % 2 == 0:
        cv2.putText(frame, ">> MESSAGE SENT <<", (w - 270, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.60, RED, 2, cv2.LINE_AA)


def draw_log_panel(frame, log_lines: list[str]):
    h, w = frame.shape[:2]
    panel_h = 90
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - panel_h), (w, h), DARK, -1)
    cv2.addWeighted(overlay, 0.70, frame, 0.30, 0, frame)

    cv2.putText(frame, "Log:", (12, h - panel_h + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1, cv2.LINE_AA)
    for i, line in enumerate(log_lines[-4:]):
        cv2.putText(frame, line, (12, h - panel_h + 36 + i * 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 230, 200), 1, cv2.LINE_AA)


def draw_skeleton(frame, mp_result):
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
    detector = PresenceDetector()

    mp_pose_draw = MP_POSE.Pose(
        static_image_mode=False,
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    log_lines: list[str] = []
    last_status   = ""
    last_log_time = 0.0
    critical_alerted = False

    print("Wandering Detector Test running — press Q in the window to quit.\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        frame = cv2.flip(frame, 1)

        # Skeleton
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_result = mp_pose_draw.process(rgb)
        draw_skeleton(frame, mp_result)

        # Presence detection
        kps    = tracker.extract_keypoints(frame)
        result = detector.update(kps)

        label, color, critical = status_from_result(
            result.absence_duration_s, result.person_present, result.wandering_detected
        )

        draw_banner(frame, label, color, result.absence_duration_s, critical)

        # ── Logging ───────────────────────────────────────────────────────────
        now = time.time()
        ts  = time.strftime("%H:%M:%S")

        if label != last_status:
            log_lines.append(f"[{ts}] {label}")
            last_status = label
            if critical and not critical_alerted:
                log_lines.append(f"[{ts}] >> ALERT: message sent to caregiver <<")
                print(f"[CRITICAL] Wandering detected at {ts} — absence {result.absence_duration_s:.1f}s")
                critical_alerted = True

        # Reset alert flag once person returns
        if result.person_present:
            critical_alerted = False

        draw_log_panel(frame, log_lines)

        cv2.imshow("Wandering Detector Test  [Q = quit]", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
