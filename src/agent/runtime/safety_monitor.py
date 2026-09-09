#the code that continuously runs the fall detector and pushes events 

from __future__ import annotations

from agent.runtime.debug_log import debug_print

import time
import threading
from concurrent.futures import ThreadPoolExecutor
import cv2

from agent.core.rules import Event, EventType
from agent.runtime.event_bus import EventBus
from agent.perception.vision.pose_tracker import PoseTracker
from agent.perception.vision.fall_detector import FallDetector
from agent.perception.vision.patient_presence import PatientPresence
from agent.runtime.patient_identity import PatientFaceClient


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
        self.presence = PatientPresence()
        self.identity = PatientFaceClient(None, patient_id)
        self._wandering_announced = False

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

        worker = ThreadPoolExecutor(max_workers=1)
        pending = None
        submitted_at = 0.0
        next_check = 0.0
        identity_status = 'waiting_for_identity'
        identity_at = 0.0
        presence = self.presence.update(identity_status, time.monotonic())

        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    self.presence.update("camera_unavailable", time.monotonic())
                    time.sleep(frame_delay)
                    continue

                kps = self.tracker.extract_keypoints(frame)
                result = self.detector.update(kps)
                clock = time.monotonic()
                if pending is not None and pending.done():
                    try:
                        pending.result()
                        identity_status = self.identity.status
                        identity_at = submitted_at
                    except Exception as exc:
                        print(f"[SafetyMonitor] Patient identity error: {exc}")
                        identity_status = 'identity_error'
                    pending = None
                    # Ignore results from old frames, including slow initial model loads.
                    status = identity_status if clock - identity_at <= 3.0 else 'identity_stale'
                    presence = self.presence.update(status, identity_at if status != 'identity_stale' else clock)
                    if status == 'patient_identified' and self._wandering_announced:
                        self.bus.publish(Event(type=EventType.SENSOR_ALERT, payload={
                            'patient_id': self.patient_id, 'wandering': False,
                            'patient_returned': True, 'wandering_conf': 0.0,
                            'wandering_reasons': ['Enrolled patient re-identified'],
                        }))
                        self._wandering_announced = False
                elif clock - identity_at > 3.0:
                    presence = self.presence.update('identity_stale', clock)
                if pending is None and clock >= next_check:
                    submitted_at = clock
                    pending = worker.submit(self.identity.identify_face, frame.copy())
                    next_check = clock + 1.0

                if result.confidence > 0.1:
                    debug_print(f"fall={result.fall_detected} conf={result.confidence:.2f} reasons={result.reasons}")
                if not presence.person_present and presence.absence_duration_s > 0:
                    debug_print(f"presence={presence.person_present} absent={presence.absence_duration_s:.1f}s wandering={presence.wandering_detected}")


                # Optional live preview for debugging
                if self.show_preview:
                    try:
                        line1 = f"fall={result.fall_detected} conf={result.confidence:.2f}"
                        line2 = f"patient={identity_status} | absent={presence.absence_duration_s:.1f}s"
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
                    self._wandering_announced = True
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

        finally:
            worker.shutdown(wait=True, cancel_futures=True)
            cap.release()
            if self.show_preview:
                cv2.destroyAllWindows()
