from __future__ import annotations

from agent.runtime.debug_log import debug_print

import threading
import time
import sys
import os
from typing import Optional

import cv2

from agent.core.rules import Event, EventType
from agent.runtime.event_bus import EventBus
from agent.toolsimplementations.tools.deepface_client import DeepFaceClient
from agent.toolsimplementations.tools.vit_face_client import ViTFaceClient
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
        voice_emotion=None,
    ) -> None:
        self.bus = bus
        self.voice_emotion = voice_emotion
        self.patient_id = patient_id
        self.camera_index = camera_index
        self.fps = fps
        self.publish_every_s = publish_every_s
        self.show_preview = show_preview

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.face_enabled = os.getenv("FACIAL_EMOTION_ENABLED", "1") != "0"
        self.face_client = None
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
        cap = cv2.VideoCapture(self.camera_index) if self.face_enabled else None
        if cap is not None and not cap.isOpened():
            print("[EmotionMonitor] Could not open camera.")
            return

        try:
            if self.face_enabled:
                # Lazily initialize DeepFace client so dev can run without it
                try:
                    backend = os.getenv("FACE_EMOTION_BACKEND", "vit").lower()
                    if backend not in ("vit", "deepface"):
                        raise ValueError("FACE_EMOTION_BACKEND must be vit or deepface")
                    self.face_client = ViTFaceClient() if backend == "vit" else DeepFaceClient()
                    from agent.runtime.patient_identity import PatientFaceClient
                    self.face_client = PatientFaceClient(self.face_client, self.patient_id)
                    debug_print(f"[EmotionMonitor] Facial classifier ready: {backend}")
                except Exception as e:
                    print(f"[EmotionMonitor] Facial classifier disabled: {e}; Python={sys.executable}. Use the project .venv and restart.")
                    self.face_client = None

            frame_interval = 1.0 / max(self.fps, 0.5)
            last_publish = 0.0

            while self._running:
                t0 = time.time()
                if cap is not None:
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
                detection_status = "initialization_failed"
                if self.face_client is not None:
                    try:
                        face_scores = self.face_client.facial_scores_from_bgr_frame(frame)
                        detection_status = self.face_client.status
                    except Exception as e:
                        print(f"[EmotionMonitor] Facial classifier error: {e}")
                        detection_status = "inference_failed"
                        face_scores = {}

                combined, source = self.voice_emotion.fuse(face_scores) if self.voice_emotion else (face_scores, "face")
                if not self.face_enabled:
                    source = "voice"
                report, debug = self.detector.build_report(
                    face_raw_scores=combined,
                )

                now = time.time()
                if (now - last_publish) >= self.publish_every_s:
                    top = sorted(face_scores.items(), key=lambda item: item[1], reverse=True)[:3]
                    debug_print(f"[EmotionMonitor] status={detection_status} face_scores={len(face_scores)} top={top} publish=True")

                    self.bus.publish(
                        Event(
                            type=EventType.EMOTION_UPDATE,
                            payload={
                                "patient_id": self.patient_id,
                                "emotion_label": str(getattr(report.emotion_label, "value", report.emotion_label)),
                                "emotion_confidence": float(report.emotion_confidence),
                                "risk_level": str(getattr(report.risk_level, "value", report.risk_level)),
                                "risk_score": float(report.risk_score),
                                "source": source,
                                "identity_status": detection_status,
                            },
                        )
                    )
                    last_publish = now

                dt = time.time() - t0
                sleep = frame_interval - dt
                if sleep > 0:
                    time.sleep(sleep)

        finally:
            if cap is not None:
                cap.release()
            if self.show_preview and cap is not None:
                cv2.destroyWindow("EmotionMonitor")
