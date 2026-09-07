from __future__ import annotations

from agent.core.rules import Event, EventType
from agent.core.brain_orchestrator import BrainOrchestrator
from models.state import SessionState


def main() -> None:
    brain = BrainOrchestrator()
    state = SessionState(patient_id="P001")

    # system start
    out = brain.handle_event(state, Event(type=EventType.SYSTEM_START))
    print("SYSTEM:", out.text_to_say)

    # patient speaks
    out = brain.handle_event(state, Event(type=EventType.PATIENT_MESSAGE, payload={"text": "I feel fine today"}))
    print("AVATAR:", out.text_to_say)

    # simulate fall alert
    out = brain.handle_event(state, Event(type=EventType.SENSOR_ALERT, payload={"fall": True, "fall_conf": 0.95}))
    print("AVATAR:", out.text_to_say)


if __name__ == "__main__":
    main()
