from agent.core.brain_orchestrator import BrainOrchestrator
from agent.core.rules import Event, EventType
from models.state import SessionState

brain = BrainOrchestrator()
state = SessionState(patient_id="P002")

out = brain.handle_event(state, Event(type=EventType.TIMER_TICK, payload={}))
print("caregiver_alert_sent:", getattr(out, "caregiver_alert_sent", False))

print("TEST patient_id:", state.patient_id)