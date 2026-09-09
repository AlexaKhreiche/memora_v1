#the code that continuously runs the fall detector and pushes events 

from __future__ import annotations

from agent.runtime.debug_log import debug_print

import time
import threading
import cv2

from agent.core.rules import Event, EventType
from agent.runtime.event_bus import EventBus
from agent.perception.vision.pose_tracker import PoseTracker
from agent.perception.vision.fall_detector import FallDetector
from agent.perception.vision.presence_detector import PresenceDetector


class SafetyMonitor:
    def __init__(
        self,
        bus: EventBus,
        patient_id: str,
        camera_index: int = 0,
        fps: float = 12.0,
        alert_cooldown_s: float = 8.0,
        show_preview: bool = False,
    ) -> None:
        self.bus = bus
        self.patient_id = patient_id
        self.camera_index = camera_index
        self.fps = fps
        self.alert_cooldown_s = alert_cooldown_s
        self.show_preview = show_preview

        self._running = False
        self._thread: threading.Thread | None = None
        self._last_fall_alert_ts = 0.0
        self._last_wander_alert_ts = 0.0

        self.tracker = PoseTracker()
        self.detector = FallDetector()
        self.presence = PresenceDetector()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            raise RuntimeError("SafetyMonitor could not open camera")

        frame_delay = 1.0 / max(1.0, self.fps)

        while self._running:
            ok, frame = cap.read()
            if not ok:
                time.sleep(frame_delay)
                continue

            kps = self.tracker.extract_keypoints(frame)
            result = self.detector.update(kps)
            presence = self.presence.update(kps)

            if result.confidence > 0.1:
                debug_print(f"fall={result.fall_detected} conf={result.confidence:.2f} reasons={result.reasons}")
            if not presence.person_present and presence.absence_duration_s > 0:
                debug_print(f"presence={presence.person_present} absent={presence.absence_duration_s:.1f}s wandering={presence.wandering_detected}")


            # Optional live preview for debugging
            if self.show_preview:
                try:
                    line1 = f"fall={result.fall_detected} conf={result.confidence:.2f}"
                    line2 = " | ".join(result.reasons[:2]) if result.reasons else ""
                    cv2.putText(frame, line1, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
                    cv2.putText(frame, line2, (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                    cv2.imshow("Safety Monitor", frame)
                    if (cv2.waitKey(1) & 0xFF) == ord("q"):
                        self._running = False
                        break
                except Exception:
                    self.show_preview = False


            # Publish events with cooldown
            now = time.time()
            if result.fall_detected and (now - self._last_fall_alert_ts) > self.alert_cooldown_s:
                self._last_fall_alert_ts = now
                self.bus.publish(
                    Event(
                        type=EventType.SENSOR_ALERT,
                        payload={
                            "patient_id": self.patient_id,
                            "fall": True,
                            "fall_conf": float(result.confidence),
                            "fall_reasons": list(result.reasons),
                        },
                    )
                )

            if presence.wandering_detected and (now - self._last_wander_alert_ts) > self.alert_cooldown_s:
                self._last_wander_alert_ts = now
                self.bus.publish(
                    Event(
                        type=EventType.SENSOR_ALERT,
                        payload={
                            "patient_id": self.patient_id,
                            "wandering": True,
                            "wandering_conf": float(presence.confidence),
                            "wandering_reasons": list(presence.reasons),
                        },
                    )
                )

            time.sleep(frame_delay)

        cap.release()
        if self.show_preview:
            cv2.destroyAllWindows()
