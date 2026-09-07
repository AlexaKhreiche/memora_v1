import time
from agent.core.brain_orchestrator import BrainOrchestrator
from agent.core.rules import Event, EventType
from models.state import SessionState

def main():
    brain = BrainOrchestrator()
    state = SessionState(patient_id="P001")

    for i in range(5):
        out = brain.handle_event(state, Event(type=EventType.TIMER_TICK, payload={}))
        print(i, "caregiver_alert_sent:", getattr(out, "caregiver_alert_sent", False))
        time.sleep(2)

if __name__ == "__main__":
    main()