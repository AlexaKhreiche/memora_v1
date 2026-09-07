# this code is for running the agent in a live setting, continuously monitoring for falls and wandering,
# and responding to events in real-time. It initializes the brain orchestrator, safety monitor, emotion monitor,
# and event bus, then enters a loop to handle incoming events and produce outputs accordingly.

from __future__ import annotations

import time
import threading
from queue import Empty

from agent.core.brain_orchestrator import BrainOrchestrator
from agent.core.rules import Event, EventType
from agent.runtime.event_bus import EventBus
from agent.runtime.safety_monitor import SafetyMonitor
from agent.runtime.browser_mic_listener import BrowserMicListener
from agent.runtime.emotion_detector import EmotionMonitor
from agent.runtime.debug_printer import (
    print_status,
    print_error,
    print_emotion_update,
    print_sensor_alert,
    print_patient_message,
    print_avatar_response,
    print_timer_tick,
    print_caregiver_alert_sent,
)
from models.state import SessionState
from dotenv import load_dotenv


class TimerPublisher:
    def __init__(self, bus: EventBus, interval_s: float = 30.0):
        self.bus = bus
        self.interval_s = interval_s
        self._running = False
        self._thread: threading.Thread | None = None

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
            time.sleep(self.interval_s)
            self.bus.publish(Event(type=EventType.TIMER_TICK, payload={}))


def main() -> None:
    patient_id = "P001"
    load_dotenv(override=True)
    bus = EventBus()
    brain = BrainOrchestrator()
    state = SessionState(patient_id=patient_id)

    out = brain.handle_event(
        state,
        Event(type=EventType.SYSTEM_START, payload={"patient_id": patient_id}),
    )

    if out is not None and out.text_to_say:
        print_avatar_response(out.text_to_say)

    monitor = SafetyMonitor(
        bus=bus,
        patient_id=patient_id,
        camera_index=0,
        fps=12.0,
        alert_cooldown_s=8.0,
        show_preview=True,
    )
    monitor.start()
    print_status("SafetyMonitor running.")

    emotion = EmotionMonitor(
        bus=bus,
        patient_id=patient_id,
        camera_index=0,
        fps=2.0,
        publish_every_s=1.0,
        show_preview=False,
    )
    emotion.start()
    print_status("EmotionMonitor running.")

    mic = BrowserMicListener(bus=bus)
    mic.start()
    print_status("BrowserMicListener running (press Ctrl+C to stop).")

    timer = TimerPublisher(bus=bus, interval_s=20.0)
    timer.start()
    print_status("TimerPublisher running.")

    try:
        while True:
            try:
                event = bus.get(timeout=0.5)
            except Empty:
                continue

            if event.type == EventType.EMOTION_UPDATE:
                print_emotion_update(event.payload)

            elif event.type == EventType.SENSOR_ALERT:
                print_sensor_alert(event.payload)

            elif event.type == EventType.PATIENT_MESSAGE:
                print_patient_message(
                    text=event.payload.get("text", ""),
                    language=event.payload.get("language"),
                    confidence=float(event.payload.get("confidence", 1.0)),
                )

            elif event.type == EventType.TIMER_TICK:
                print_timer_tick()

            out = brain.handle_event(state, event)

            if out is None:
                time.sleep(0.05)
                continue

            if getattr(out, "caregiver_alert_sent", False):
                print_caregiver_alert_sent()

            if out.text_to_say:
                print_avatar_response(out.text_to_say)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print_error(str(e))
    finally:
        try:
            mic.stop()
        except Exception:
            pass
        try:
            monitor.stop()
        except Exception:
            pass
        try:
            emotion.stop()
        except Exception:
            pass
        try:
            timer.stop()
        except Exception:
            pass

        print_status("Stopped.")
        raise SystemExit(0)


if __name__ == "__main__":
    main()