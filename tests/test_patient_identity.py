import pytest
from agent.runtime.patient_identity import select_match, reference_path


def test_selects_patient_with_bystanders():
    assert select_match([0.8, 0.2, 0.9]) == 1


def test_rejects_absent_or_ambiguous_identity():
    assert select_match([]) is None
    assert select_match([0.7, 0.8]) is None
    assert select_match([0.2, 0.25]) is None
    assert select_match([float('nan')]) is None


def test_reference_path_rejects_traversal():
    with pytest.raises(ValueError):
        reference_path('../P001')


def test_only_matched_crop_reaches_emotion_model(tmp_path, monkeypatch):
    import json
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock
    import numpy as np
    import agent.runtime.patient_identity as identity
    monkeypatch.setattr(identity, 'ROOT', tmp_path)
    ref = identity.reference_path('P001')
    ref.parent.mkdir(parents=True)
    vector = np.zeros(128); vector[0] = 1
    ref.write_text(json.dumps({'model': 'SFace', 'embedding': vector.tolist()}))
    patient = np.full((20, 20, 3), 200, dtype=np.uint8)
    bystander = np.zeros((20, 20, 3), dtype=np.uint8)
    monkeypatch.setitem(sys.modules, 'deepface', SimpleNamespace(DeepFace=SimpleNamespace(
        extract_faces=lambda **kwargs: [{'face': bystander}, {'face': patient}])))
    other = np.zeros(128); other[1] = 1
    monkeypatch.setattr(identity, 'embedding', lambda crop: vector if crop is patient else other)
    classifier = Mock(status='ok')
    classifier.facial_scores_from_bgr_frame.return_value = {'happy': 0.9}
    client = identity.PatientFaceClient(classifier, 'P001')
    assert client.facial_scores_from_bgr_frame(None) == {'happy': 0.9}
    np.testing.assert_array_equal(classifier.facial_scores_from_bgr_frame.call_args.args[0], patient)
    assert client.status == 'patient_identified'
    ref.unlink()
    classifier.reset_mock()
    assert client.facial_scores_from_bgr_frame(None) == {}
    classifier.facial_scores_from_bgr_frame.assert_not_called()
    assert client.status == 'patient_not_enrolled'
