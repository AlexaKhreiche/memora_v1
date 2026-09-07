from agent.core.brain_orchestrator import BrainOrchestrator
from agent.core.rules import Event, EventType
from models.state import SessionState


def show(title, out, state):
    print(f"\n{'=' * 20} {title} {'=' * 20}")
    print("text_to_say:", repr(out.text_to_say))
    print("avatar_actions:", out.avatar_actions)
    print("caregiver_alert_sent:", getattr(out, "caregiver_alert_sent", False))
    print("last_decision:", state.last_decision.action if state.last_decision else None)
    print("phase:", state.phase)


brain = BrainOrchestrator()
state = SessionState(patient_id="P002")

# 1) Start system
event = Event(type=EventType.SYSTEM_START, payload={})
out = brain.handle_event(state, event)
show("SYSTEM_START", out, state)

# 2) Happy / chatty message -> should go to conversation
event = Event(
    type=EventType.PATIENT_MESSAGE,
    payload={
        "text": "I am feeling very good today and I want to talk",
        "confidence": 0.95,
        "language": "en",
        "prosody_label": "happy",
        "prosody_confidence": 0.90,
    },
)
out = brain.handle_event(state, event)
show("HAPPY / CHATTY", out, state)

# 3) Agitated message -> should go to de-escalation
event = Event(
    type=EventType.PATIENT_MESSAGE,
    payload={
        "text": "Leave me alone, I am upset",
        "confidence": 0.95,
        "language": "en",
        "prosody_label": "agitated",
        "prosody_confidence": 0.95,
    },
)
out = brain.handle_event(state, event)
show("AGITATED", out, state)

# 4) Fall event -> should go to fall protocol + caregiver alert
event = Event(
    type=EventType.SENSOR_ALERT,
    payload={
        "fall": True,
        "fall_conf": 0.95,
        "wandering": False,
        "wandering_conf": 0.0,
    },
)
out = brain.handle_event(state, event)
show("FALL", out, state)

# 5) Wandering event -> should be caregiver alert only, no speech
event = Event(
    type=EventType.SENSOR_ALERT,
    payload={
        "fall": False,
        "fall_conf": 0.0,
        "wandering": True,
        "wandering_conf": 0.95,
    },
)
out = brain.handle_event(state, event)
show("WANDERING", out, state)