from utils.caregiver_updates import mark_activity_completed
from models.state import SessionState
from agent.toolsimplementations.tools.daily_reminder_tool import check_caregiver_schedule

def main():
    patient_id = "P002"
    mark_activity_completed(patient_id, "walk")  # mark it done

    state = SessionState(patient_id=patient_id)
    report = check_caregiver_schedule(state)
    print("reminders_due:", report.reminders_due)

if __name__ == "__main__":
    main()