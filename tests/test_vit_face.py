from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
from agent.toolsimplementations.tools.vit_face_client import ViTFaceClient


def test_crop_and_model_preprocessing():
    import torch
    client = ViTFaceClient.__new__(ViTFaceClient)
    crop = np.full((48, 48, 3), 128, dtype=np.uint8)
    client.extract_faces = Mock(return_value=[{'face': crop}])
    client.processor = Mock(return_value={'pixel_values': torch.zeros(1, 3, 224, 224)})
    client.model = Mock(return_value=SimpleNamespace(logits=torch.tensor([[0., 2.]])))
    client.model.config = SimpleNamespace(id2label={0: 'sad', 1: 'neutral'})
    scores = client.facial_scores_from_bgr_frame(crop)
    assert max(scores, key=scores.get) == 'neutral'
    assert sum(scores.values()) == pytest.approx(1)
    assert client.processor.call_args.kwargs['images'] is crop
    assert client.extract_faces.call_args.kwargs['normalize_face'] is False
    assert client.extract_faces.call_args.kwargs['color_face'] == 'rgb'


@pytest.mark.parametrize('faces', [[], [{'face': None}, {'face': None}]])
def test_missing_or_multiple_faces_skip_classifier(faces):
    client = ViTFaceClient.__new__(ViTFaceClient)
    client.extract_faces = Mock(return_value=faces)
    client.processor = Mock()
    assert client.facial_scores_from_bgr_frame(None) == {}
    client.processor.assert_not_called()
