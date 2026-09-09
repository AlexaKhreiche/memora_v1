from __future__ import annotations

import json
import time
import threading
from pathlib import Path

from agent.core.rules import Event, EventType
from agent.runtime.event_bus import EventBus


class BrowserMicListener:
    """
    Reads transcript JSON files written by the frontend and publishes
    PATIENT_MESSAGE events onto the EventBus in the same shape as MicListener.
    """

    def __init__(self, bus: EventBus, poll_interval_s: float = 0.1, voice_emotion=None) -> None:
        self.bus = bus
        self.voice_emotion = voice_emotion
        self.poll_interval_s = poll_interval_s
        self._running = False
        self._thread: threading.Thread | None = None

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _queue_dir(self) -> Path:
        q = self._project_root() / "data" / "incoming_transcripts"
        q.mkdir(parents=True, exist_ok=True)
        return q

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while self._running:
            queue_dir = self._queue_dir()
            files = sorted(queue_dir.glob("msg_*.json"))

            for file_path in files:
                try:
                    with file_path.open("r", encoding="utf-8") as f:
                        payload = json.load(f)

                    transcript = str(payload.get("transcript", "")).strip()
                    confidence = float(payload.get("confidence", 1.0))
                    language = str(payload.get("language", "unknown"))

                    if transcript:
                        if self.voice_emotion is not None:
                            self.voice_emotion.submit(payload)
                        self.bus.publish(
                            Event(
                                type=EventType.PATIENT_MESSAGE,
                                payload={
                                    "text": transcript,
                                    "confidence": confidence,
                                    "language": language,
                                },
                            )
                        )

                    file_path.unlink(missing_ok=True)

                except Exception as e:
                    print(f"[BrowserMicListener] Failed to process {file_path.name}: {e}")

            time.sleep(self.poll_interval_s)