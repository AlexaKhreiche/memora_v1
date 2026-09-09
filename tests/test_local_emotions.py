from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent.toolsimplementations.tools.deepface_client import DeepFaceClient
from agent.toolsimplementations.tools.emotion_safety_detector import EmotionSafetyDetector
from agent.core.brain_orchestrator import BrainOrchestrator


def client_with(result=None, error=None):
    client = DeepFaceClient.__new__(DeepFaceClient)
    client.analyze = Mock(return_value=result, side_effect=error)
    return client


def test_percentage_conversion_and_mapping():
    client = client_with([{"emotion": {"angry": 80, "neutral": 20}}])
    scores = client.facial_scores_from_bgr_frame(object())
    report, _ = EmotionSafetyDetector().build_report(scores)
    assert report.emotion_label.value == "agitated"
    assert report.emotion_confidence == pytest.approx(0.8)
    assert client.analyze.call_args.kwargs["actions"] == ["emotion"]
    assert client.analyze.call_args.kwargs["enforce_detection"] is True


@pytest.mark.parametrize("faces", [[], [{"emotion": {"happy": 90}}] * 2])
def test_absent_or_ambiguous_face_is_uncertain(faces):
    scores = client_with(faces).facial_scores_from_bgr_frame(object())
    report, _ = EmotionSafetyDetector().build_report(scores)
    assert report.emotion_label.value == "uncertain"
    assert report.emotion_confidence == 0


def test_no_face_exception_is_empty_but_other_failures_propagate():
    assert client_with(error=ValueError("Face could not be detected in numpy array")).facial_scores_from_bgr_frame(None) == {}
    with pytest.raises(ValueError, match="bad model"):
        client_with(error=ValueError("bad model")).facial_scores_from_bgr_frame(None)


def test_stable_confidence_does_not_inflate_repetition():
    state = SimpleNamespace(emotion_history=[{"label": "neutral", "confidence": 0.5}] * 5)
    assert BrainOrchestrator._compute_stable_emotion(None, state) == ("neutral", 0.5)
    state.emotion_history.append({"label": "uncertain", "confidence": 0})
    assert BrainOrchestrator._compute_stable_emotion(None, state) == ("uncertain", 0)


@pytest.mark.parametrize('label, mode', [
    ('calm', 'reminiscence'), ('neutral', 'reminiscence'), ('sad', 'reminiscence'),
    ('anxious', 'de_escalation'), ('distressed', 'de_escalation'), ('agitated', 'de_escalation'),
    ('happy', 'conversation'), ('confused', 'conversation'),
])
def test_dashboard_and_decision_share_existing_emotion_routes(label, mode):
    from agent.core.rules import _emotion_to_mode
    state = SimpleNamespace(emotion_history=[{'label': label, 'confidence': 0.8}])
    assert _emotion_to_mode(label) == mode
    assert BrainOrchestrator._compute_intervention_group(None, state) == mode


def test_empty_observation_does_not_default_to_de_escalation():
    state = SimpleNamespace(emotion_history=[{'label': 'uncertain', 'confidence': 0}])
    assert BrainOrchestrator._compute_intervention_group(None, state) == 'conversation'

