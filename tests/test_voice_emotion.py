from agent.runtime.voice_emotion import VoiceEmotion


def test_fusion_and_expiry():
    voice = VoiceEmotion()
    voice.scores = {'happy': 0.8, 'neutral': 0.2}
    voice.observed_at = 100
    assert voice.fuse({'happy': 0.4, 'sad': 0.6}, now=105) == ({'happy': 0.6000000000000001, 'neutral': 0.1, 'sad': 0.3}, 'face+voice')
    assert voice.fuse({}, now=105) == (voice.scores, 'voice')
    assert voice.fuse({'sad': 0.9}, now=111) == ({'sad': 0.9}, 'face')


def test_queue_is_bounded_and_language_gated():
    voice = VoiceEmotion()
    voice.submit({'language': 'french', 'audio_base64': 'AAAA'})
    assert voice.jobs.empty()
    voice.submit({'language': 'english', 'audio_base64': 'AAAA'})
    voice.submit({'language': 'en', 'audio_base64': 'BBBB'})
    assert voice.jobs.qsize() == 1
    assert voice.jobs.get()[0] == 'BBBB'
