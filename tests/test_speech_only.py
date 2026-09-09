from unittest.mock import Mock, patch
from agent.runtime.emotion_detector import EmotionMonitor


def test_voice_only_does_not_open_camera_or_initialize_face(monkeypatch):
    monkeypatch.setenv('FACIAL_EMOTION_ENABLED', '0')
    bus = Mock()
    voice = Mock()
    voice.fuse.return_value = ({'happy': 0.8}, 'voice')
    monitor = EmotionMonitor(bus, 'P001', voice_emotion=voice)
    monitor._running = True
    bus.publish.side_effect = lambda event: setattr(monitor, '_running', False)
    with patch('agent.runtime.emotion_detector.cv2.VideoCapture') as camera, patch('agent.runtime.emotion_detector.ViTFaceClient') as face, patch('agent.runtime.emotion_detector.time.sleep'):
        monitor._loop()
    camera.assert_not_called()
    face.assert_not_called()
    event = bus.publish.call_args.args[0]
    assert event.payload['source'] == 'voice'
    assert event.payload['emotion_label'] == 'happy'
