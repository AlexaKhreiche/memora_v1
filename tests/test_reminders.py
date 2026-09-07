from models.state import SessionState
from agent.toolsimplementations.tools.daily_reminder_tool import check_caregiver_schedule

def main():
    state = SessionState(patient_id="P002")

    report = check_caregiver_schedule(state)
    print("reminders_due:", report.reminders_due)
    print("next_reminder_iso:", report.next_reminder_iso)
    print("TEST patient_id:", state.patient_id)

if __name__ == "__main__":
    main()
    
    