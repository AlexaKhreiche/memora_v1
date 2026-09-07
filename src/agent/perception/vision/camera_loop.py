from __future__ import annotations

import cv2
import time

from .pose_tracker import PoseTracker
from .fall_detector import FallDetector


def run_camera_fall_demo(camera_index: int = 0) -> None:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera")

    tracker = PoseTracker()
    detector = FallDetector()

    last_print = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        kps = tracker.extract_keypoints(frame)
        result = detector.update(kps)

        # ====== SHOW IN WINDOW ======
        if kps is None:
            line1 = "pose=None"
            line2 = "fall=False conf=0.00"
        else:
            line1 = f"fall={result.fall_detected} conf={result.confidence:.2f}"
            line2 = " | ".join(result.reasons[:2]) if result.reasons else "no_reasons"

        cv2.putText(frame, line1, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        cv2.putText(frame, line2, (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # ====== PRINT IN TERMINAL WHEN FALL DETECTED ======
        if result.fall_detected:
            now = time.time()
            if now - last_print > 1.0:  # throttle spam
                last_print = now
                print(f"[FALL DETECTED] conf={result.confidence:.2f} reasons={result.reasons}")

        cv2.imshow("Fall Detector Demo", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
