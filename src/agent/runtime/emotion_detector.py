from __future__ import annotations

import threading
import time
from typing import Optional

import cv2

from agent.core.rules import Event, EventType
from agent.runtime.event_bus import EventBus
from agent.toolsimplementations.tools.hume_http import HumeHTTPClient
from agent.toolsimplementations.tools.emotion_safety_detector import EmotionSafetyDetector


class EmotionMonitor:
    """
    Continuous non-verbal emotion monitoring using camera frames.
    Publishes EMOTION_UPDATE events with fused emotion derived from face stream only.
    """

    def __init__(
        self,
        bus: EventBus,
        patient_id: str,
        camera_index: int = 0,
        fps: float = 2.0,               # low FPS is enough for emotion; keeps CPU low
        publish_every_s: float = 1.0,   # publish frequency
        show_preview: bool = False,
    ) -> None:
        self.bus = bus
        self.patient_id = patient_id
        self.camera_index = camera_index
        self.fps = fps
        self.publish_every_s = publish_every_s
        self.show_preview = show_preview

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.hume = None
        self.detector = EmotionSafetyDetector()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print("[EmotionMonitor] Could not open camera.")
            return

        try:
            # Lazily initialize Hume client so dev can run without it
            try:
                self.hume = HumeHTTPClient()
                print("[EmotionMonitor] Hume client initialized.")
            except Exception as e:
                print(f"[EmotionMonitor] Hume disabled: {e}")
                self.hume = None

            frame_interval = 1.0 / max(self.fps, 0.5)
            last_publish = 0.0

            while self._running:
                t0 = time.time()
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.1)
                    continue

                if self.show_preview:
                    cv2.imshow("EmotionMonitor", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        self._running = False
                        break

                face_scores = {}
                if self.hume is not None:
                    try:
                        face_scores = self.hume.facial_scores_from_bgr_frame(frame)
                    except Exception as e:
                        print(f"[EmotionMonitor] Hume face error: {e}")
                        face_scores = {}

                report, debug = self.detector.build_report(
                    face_raw_scores=face_scores,
                )

                now = time.time()
                if (now - last_publish) >= self.publish_every_s:
                    print(f"[EmotionMonitor] face_scores={len(face_scores)} publish=True")

                    self.bus.publish(
                        Event(
                            type=EventType.EMOTION_UPDATE,
                            payload={
                                "patient_id": self.patient_id,
                                "emotion_label": str(getattr(report.emotion_label, "value", report.emotion_label)),
                                "emotion_confidence": float(report.emotion_confidence),
                                "risk_level": str(getattr(report.risk_level, "value", report.risk_level)),
                                "risk_score": float(report.risk_score),
                                "source": "face",
                            },
                        )
                    )
                    last_publish = now

                dt = time.time() - t0
                sleep = frame_interval - dt
                if sleep > 0:
                    time.sleep(sleep)

        finally:
            cap.release()
            if self.show_preview:
                cv2.destroyWindow("EmotionMonitor")