from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Dict, Optional

import agent.core.brain_orchestrator as brain_module
from models.state import SessionState
from agent.core.brain_orchestrator import BrainOrchestrator
from agent.core.rules import Event, EventType


PATIENT_ID = "P001"


SCENARIOS = {
    "calm": {
        "description": "Neutral emotion + normal message -> conversation",
        "emotion_label": "neutral",
        "emotion_confidence": 0.85,
        "risk_level": "low",
        "risk_score": 0.15,
        "emotion_updates": 4,
        "message_text": "Hello, how are you?",
        "expected_action": "conversation",
        "stability_seconds": 0.0,
    },
    "happy": {
        "description": "Happy emotion + normal message -> conversation",
        "emotion_label": "happy",
        "emotion_confidence": 0.85,
        "risk_level": "low",
        "risk_score": 0.10,
        "emotion_updates": 4,
        "message_text": "I am feeling good today.",
        "expected_action": "conversation",
        "stability_seconds": 0.0,
    },
    "agitation": {
        "description": "Sustained agitation -> de_escalation",
        "emotion_label": "agitated",
        "emotion_confidence": 0.90,
        "risk_level": "high",
        "risk_score": 0.80,
        "emotion_updates": 5,
        "message_text": "Leave me alone.",
        "expected_action": "de_escalation",
        "stability_seconds": 3.0,
    },
    "distress": {
        "description": "Sustained distress -> de_escalation",
        "emotion_label": "distressed",
        "emotion_confidence": 0.90,
        "risk_level": "high",
        "risk_score": 0.85,
        "emotion_updates": 5,
        "message_text": "I do not feel safe.",
        "expected_action": "de_escalation",
        "stability_seconds": 3.0,
    },
    "reminiscence": {
        "description": "Sustained calm state -> reminiscence",
        "emotion_label": "calm",
        "emotion_confidence": 0.90,
        "risk_level": "medium",
        "risk_score": 0.50,
        "emotion_updates": 7,
        "message_text": "I miss the old days.",
        "expected_action": "reminiscence",
        "stability_seconds": 5.0,
    },
    "sad": {
        "description": "Sustained sadness -> reminiscence",
        "emotion_label": "sad",
        "emotion_confidence": 0.90,
        "risk_level": "medium",
        "risk_score": 0.55,
        "emotion_updates": 7,
        "message_text": "I miss my family.",
        "expected_action": "reminiscence",
        "stability_seconds": 5.0,
    },
    "anxious": {
        "description": "Sustained anxiety -> reminiscence",
        "emotion_label": "anxious",
        "emotion_confidence": 0.90,
        "risk_level": "medium",
        "risk_score": 0.60,
        "emotion_updates": 7,
        "message_text": "I feel uneasy.",
        "expected_action": "reminiscence",
        "stability_seconds": 5.0,
    },
    "fall": {
        "description": "Immediate fall safety override",
        "expected_action": "fall_protocol",
        "stability_seconds": 0.0,
    },
    "wandering": {
        "description": "Immediate wandering safety override",
        "expected_action": "wandering_alert",
        "stability_seconds": 0.0,
    },
    "mixed": {
        "description": "Conversation -> de_escalation -> wandering",
        "expected_action": "mixed",
        "stability_seconds": 0.0,
    },
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def results_csv_path() -> Path:
    path = project_root() / "data" / "tests" / "scenario_results.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def action_name(action: Any) -> str:
    if action is None:
        return ""
    if hasattr(action, "value"):
        return str(action.value).strip().lower()
    return str(action).strip().lower()


def write_result_row(row: Dict[str, Any]) -> None:
    path = results_csv_path()
    fieldnames = [
        "scenario",
        "run",
        "description",
        "expected_action",
        "actual_action",
        "correct",
        "caregiver_alert_sent",
        "condition_start",
        "threshold_satisfied_at",
        "decision_time",
        "switch_delay_after_threshold_s",
        "notes",
    ]

    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k) for k in fieldnames})


def dispatch_event(
    brain: BrainOrchestrator,
    state: SessionState,
    event_type: EventType,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    event = Event(type=event_type, payload=payload or {})
    brain.handle_event(state, event)


def new_session() -> tuple[BrainOrchestrator, SessionState]:
    # Disable reminder interference during controlled testing
    brain_module.check_caregiver_schedule = lambda state: None

    brain = BrainOrchestrator()
    state = SessionState(patient_id=PATIENT_ID)
    state.last_reminders = None

    dispatch_event(
        brain=brain,
        state=state,
        event_type=EventType.SYSTEM_START,
        payload={},
    )
    return brain, state


def run_emotion_sequence(
    brain: BrainOrchestrator,
    state: SessionState,
    *,
    emotion_label: str,
    emotion_confidence: float,
    risk_level: str,
    risk_score: float,
    updates: int,
    interval_s: float = 1.0,
) -> float:
    condition_start = time.perf_counter()

    for _ in range(updates):
        dispatch_event(
            brain=brain,
            state=state,
            event_type=EventType.EMOTION_UPDATE,
            payload={
                "patient_id": state.patient_id,
                "emotion_label": emotion_label,
                "emotion_confidence": emotion_confidence,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "source": "scenario_runner",
            },
        )
        time.sleep(interval_s)

    return condition_start


def run_patient_message(
    brain: BrainOrchestrator,
    state: SessionState,
    text: str,
) -> tuple[str, bool, float]:
    decision_time = time.perf_counter()

    dispatch_event(
        brain=brain,
        state=state,
        event_type=EventType.PATIENT_MESSAGE,
        payload={
            "text": text,
            "confidence": 1.0,
            "language": "en",
        },
    )

    actual_action = action_name(getattr(state.last_decision, "action", None))
    caregiver_alert_sent = bool(state.last_ui_payload.get("caregiver_alert_sent", False))
    return actual_action, caregiver_alert_sent, decision_time


def run_fall(
    brain: BrainOrchestrator,
    state: SessionState,
) -> tuple[str, bool, float, float]:
    condition_start = time.perf_counter()

    dispatch_event(
        brain=brain,
        state=state,
        event_type=EventType.SENSOR_ALERT,
        payload={
            "patient_id": state.patient_id,
            "fall": True,
            "fall_conf": 0.95,
            "fall_reasons": ["scenario_runner simulated fall"],
        },
    )

    decision_time = time.perf_counter()
    actual_action = action_name(getattr(state.last_decision, "action", None))
    caregiver_alert_sent = bool(state.last_ui_payload.get("caregiver_alert_sent", False))
    return actual_action, caregiver_alert_sent, condition_start, decision_time


def run_wandering(
    brain: BrainOrchestrator,
    state: SessionState,
) -> tuple[str, bool, float, float]:
    condition_start = time.perf_counter()

    dispatch_event(
        brain=brain,
        state=state,
        event_type=EventType.SENSOR_ALERT,
        payload={
            "patient_id": state.patient_id,
            "wandering": True,
            "wandering_conf": 0.95,
            "wandering_reasons": ["scenario_runner simulated wandering"],
        },
    )

    decision_time = time.perf_counter()
    actual_action = action_name(getattr(state.last_decision, "action", None))
    caregiver_alert_sent = bool(state.last_ui_payload.get("caregiver_alert_sent", False))
    return actual_action, caregiver_alert_sent, condition_start, decision_time


def run_one_scenario(name: str, run_number: int) -> None:
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {name}")

    scenario = SCENARIOS[name]
    brain, state = new_session()

    expected_action = scenario["expected_action"]
    description = scenario["description"]
    notes = ""

    if name in {"calm", "happy", "agitation", "distress", "reminiscence", "sad", "anxious"}:
        condition_start = run_emotion_sequence(
            brain=brain,
            state=state,
            emotion_label=scenario["emotion_label"],
            emotion_confidence=scenario["emotion_confidence"],
            risk_level=scenario["risk_level"],
            risk_score=scenario["risk_score"],
            updates=scenario["emotion_updates"],
            interval_s=1.0,
        )

        threshold_satisfied_at = condition_start + scenario["stability_seconds"]

        actual_action, caregiver_alert_sent, decision_time = run_patient_message(
            brain=brain,
            state=state,
            text=scenario["message_text"],
        )

        switch_delay = decision_time - threshold_satisfied_at

    elif name == "fall":
        actual_action, caregiver_alert_sent, condition_start, decision_time = run_fall(
            brain=brain,
            state=state,
        )
        threshold_satisfied_at = condition_start
        switch_delay = decision_time - threshold_satisfied_at

    elif name == "wandering":
        actual_action, caregiver_alert_sent, condition_start, decision_time = run_wandering(
            brain=brain,
            state=state,
        )
        threshold_satisfied_at = condition_start
        switch_delay = decision_time - threshold_satisfied_at

    elif name == "mixed":
        # Phase 1: conversation
        run_emotion_sequence(
            brain=brain,
            state=state,
            emotion_label="neutral",
            emotion_confidence=0.85,
            risk_level="low",
            risk_score=0.20,
            updates=7,
            interval_s=1.0,
        )
        conv_action, _, _ = run_patient_message(brain, state, "Hello there.")

        # Phase 2: de-escalation
        condition_start = run_emotion_sequence(
            brain=brain,
            state=state,
            emotion_label="agitated",
            emotion_confidence=0.90,
            risk_level="high",
            risk_score=0.80,
            updates=5,
            interval_s=1.0,
        )
        threshold_satisfied_at = condition_start + 3.0
        time.sleep(2.5)
        actual_action, caregiver_alert_sent, decision_time = run_patient_message(
            brain=brain,
            state=state,
            text="Please stop.",
        )
        switch_delay = decision_time - threshold_satisfied_at

        # Phase 3: wandering override
        dispatch_event(
            brain=brain,
            state=state,
            event_type=EventType.SENSOR_ALERT,
            payload={
                "patient_id": state.patient_id,
                "wandering": True,
                "wandering_conf": 0.95,
                "wandering_reasons": ["scenario_runner mixed scenario wandering"],
            },
        )

        notes = (
            f"Phase1={conv_action}; "
            f"Phase2={actual_action}; "
            f"Phase3=wandering_alert expected"
        )

    else:
        raise ValueError(f"Unhandled scenario: {name}")

    correct = False
    if name == "wandering":
        correct = actual_action in {"wandering_alert", "wandering_protocol"}
    elif name == "fall":
        correct = actual_action == "fall_protocol"
    elif name == "mixed":
        correct = actual_action == "de_escalation"
    else:
        correct = actual_action == expected_action

    row = {
        "scenario": name,
        "run": run_number,
        "description": description,
        "expected_action": expected_action,
        "actual_action": actual_action,
        "correct": correct,
        "caregiver_alert_sent": caregiver_alert_sent,
        "condition_start": f"{condition_start:.6f}",
        "threshold_satisfied_at": f"{threshold_satisfied_at:.6f}",
        "decision_time": f"{decision_time:.6f}",
        "switch_delay_after_threshold_s": f"{switch_delay:.6f}",
        "notes": notes,
    }

    write_result_row(row)
    print(
        f"✅ scenario={name} run={run_number} "
        f"expected={expected_action} actual={actual_action} correct={correct}"
    )


def run_batch(scenario_name: str, runs: int = 3) -> None:
    for i in range(1, runs + 1):
        run_one_scenario(scenario_name, i)


def main() -> None:
    run_batch("calm", runs=3)
    run_batch("happy", runs=3)

    run_batch("agitation", runs=3)
    run_batch("distress", runs=3)

    run_batch("reminiscence", runs=3)
    run_batch("sad", runs=3)
    run_batch("anxious", runs=3)

    run_batch("fall", runs=3)
    run_batch("wandering", runs=3)
    run_batch("mixed", runs=3)

    print(f"\nResults saved to: {results_csv_path()}")


if __name__ == "__main__":
    main()