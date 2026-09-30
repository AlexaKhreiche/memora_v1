from agent.runtime.voice_emotion import VoiceEmotion
import pytest


def test_fusion_and_expiry():
    voice = VoiceEmotion()
    voice.scores = {'happy': 0.8, 'neutral': 0.2}
    voice.observed_at = 100
    scores, source = voice.fuse({'happy': 0.4, 'sad': 0.6}, now=105)
    assert scores == pytest.approx({'happy': 0.72, 'neutral': 0.16, 'sad': 0.12})
    assert source == 'face+voice'
    assert voice.fuse({}, now=105) == (voice.scores, 'voice')
    assert voice.fuse({'sad': 0.9}, now=111) == ({'sad': 0.9}, 'face')


def test_neutral_voice_outweighs_fearful_face():
    from agent.toolsimplementations.tools.emotion_safety_detector import EmotionSafetyDetector

    voice = VoiceEmotion()
    voice.scores = {'neutral': 0.9, 'sad': 0.1}
    voice.observed_at = 100
    scores, _ = voice.fuse({'fear': 0.99, 'neutral': 0.01}, now=105)
    report, _ = EmotionSafetyDetector().build_report(scores)
    assert report.emotion_label.value == 'neutral'
    assert report.risk_level.value == 'low'


@pytest.mark.parametrize('fear, expected', [(0.4, 'uncertain'), (0.84, 'uncertain'),
                                           (0.85, 'distressed'), (0.95, 'distressed')])
def test_face_only_distress_requires_strong_evidence(fear, expected):
    from agent.toolsimplementations.tools.emotion_safety_detector import EmotionSafetyDetector

    voice = VoiceEmotion()
    voice.scores = {'neutral': 1.0}
    voice.observed_at = 100
    scores, source = voice.fuse({'fear': fear, 'neutral': 0.1}, now=111)
    report, _ = EmotionSafetyDetector().build_report(scores)
    assert source == 'face'
    assert report.emotion_label.value == expected
    if expected == 'uncertain':
        assert report.emotion_confidence == 0
        assert report.risk_level.value == 'low'


def test_queue_is_bounded_and_language_gated():
    voice = VoiceEmotion()
    voice.submit({'language': 'french', 'audio_base64': 'AAAA'})
    assert voice.jobs.empty()
    voice.submit({'language': 'english', 'audio_base64': 'AAAA'})
    voice.submit({'language': 'en', 'audio_base64': 'BBBB'})
    assert voice.jobs.qsize() == 1
    assert voice.jobs.get()[0] == 'BBBB'
