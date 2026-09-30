from agent.perception.vision.patient_presence import PatientPresence


def test_bystander_alone_does_not_start_session_timer():
    detector = PatientPresence()
    assert not detector.update('identity_uncertain', 0).wandering_detected
    assert not detector.update('identity_uncertain', 100).wandering_detected


def test_patient_leaves_while_bystander_stays_then_returns():
    detector = PatientPresence()
    assert detector.update('patient_identified', 0).person_present
    assert not detector.update('identity_uncertain', 7).wandering_detected
    result = detector.update('identity_uncertain', 8)
    assert result.wandering_detected
    assert result.confidence == 0.7
    assert not detector.update('patient_identified', 10).wandering_detected
    assert not detector.update('patient_not_visible', 11).wandering_detected


def test_identity_outage_is_not_wandering():
    detector = PatientPresence()
    detector.update('patient_identified', 0)
    detector.update('identity_error', 10)
    assert not detector.update('patient_not_visible', 20).wandering_detected
    detector.update('patient_identified', 21)
    assert detector.update('patient_not_visible', 30).wandering_detected


def test_patient_return_clears_wandering_without_clearing_fall():
    from unittest.mock import Mock
    from models.state import SessionState
    from agent.core.brain_orchestrator import BrainOrchestrator
    from agent.core.rules import Event, EventType
    brain = BrainOrchestrator.__new__(BrainOrchestrator)
    brain._append_safety_log = Mock()
    brain._finalize_output = Mock()
    state = SessionState(patient_id='P001', wandering_active=True, fall_active=True)
    brain._handle_sensor_alert(state, Event(type=EventType.SENSOR_ALERT,
        payload={'patient_returned': True, 'wandering': False}))
    assert not state.wandering_active
    assert state.fall_active
    brain._finalize_output.assert_called_once()
