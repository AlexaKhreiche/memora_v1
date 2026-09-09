"""Local reference enrollment and per-frame patient verification (SFace)."""
import json
import re
import os
from pathlib import Path
from uuid import uuid4
import numpy as np
from agent.runtime.model_loading import MODEL_LOAD_LOCK

ROOT = Path(__file__).resolve().parents[3]


def reference_path(patient_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', patient_id):
        raise ValueError('Invalid patient ID')
    return ROOT / 'data' / 'patients' / patient_id / 'identity' / 'reference.json'


def embedding(rgb):
    from deepface import DeepFace
    with MODEL_LOAD_LOCK:
        result = DeepFace.represent(img_path=np.ascontiguousarray(rgb[:, :, ::-1]),
            model_name='SFace', detector_backend='skip', enforce_detection=False, align=False)
    vector = np.asarray(result[0]['embedding'], dtype=float)
    norm = np.linalg.norm(vector)
    if not np.isfinite(vector).all() or norm <= 0:
        raise ValueError('Invalid face embedding')
    return vector / norm


def enroll(patient_id, image_path):
    from deepface import DeepFace
    faces = DeepFace.extract_faces(img_path=str(image_path), detector_backend='opencv',
        enforce_detection=True, align=True, color_face='rgb', normalize_face=False)
    if len(faces) != 1:
        raise ValueError('Reference photo must contain exactly one clearly visible face')
    vector = embedding(faces[0]['face'])
    target = reference_path(patient_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f'{uuid4().hex}.tmp')
    try:
        with temporary.open('x') as f:
            os.chmod(temporary, 0o600)
            json.dump({'model': 'SFace', 'embedding': vector.tolist()}, f)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def select_match(distances, threshold=0.593, margin=0.10):
    ordered = sorted(enumerate(distances), key=lambda item: item[1])
    if not ordered or not np.isfinite(ordered[0][1]) or ordered[0][1] > threshold:
        return None
    if len(ordered) > 1 and ordered[1][1] - ordered[0][1] < margin:
        return None
    return ordered[0][0]


class PatientFaceClient:
    def __init__(self, client, patient_id):
        self.client = client
        self.path = reference_path(patient_id)
        self.status = 'patient_not_enrolled'

    def identify_face(self, frame):
        from deepface import DeepFace
        self.status = 'identity_error'
        if not self.path.exists():
            self.status = 'patient_not_enrolled'
            return None
        data = json.loads(self.path.read_text())
        if data.get('model') != 'SFace':
            raise ValueError('Reference model mismatch; re-enroll patient')
        reference = np.asarray(data['embedding'], dtype=float)
        if reference.shape != (128,) or not np.isfinite(reference).all() or np.linalg.norm(reference) <= 0:
            raise ValueError('Invalid reference; re-enroll patient')
        reference = reference / np.linalg.norm(reference)
        try:
            faces = DeepFace.extract_faces(img_path=frame, detector_backend='opencv',
                enforce_detection=True, align=True, color_face='rgb', normalize_face=False)
        except ValueError as exc:
            if 'face could not be detected' in str(exc).lower():
                self.status = 'patient_not_visible'
                return None
            raise
        distances = [float(1 - np.dot(reference, embedding(face['face']))) for face in faces]
        selected = select_match(distances)
        if selected is None:
            self.status = 'identity_uncertain'
            return None
        self.status = 'patient_identified'
        return np.ascontiguousarray(faces[selected]['face'][:, :, ::-1])

    def facial_scores_from_bgr_frame(self, frame):
        crop = self.identify_face(frame)
        if crop is None:
            return {}
        scores = self.client.facial_scores_from_bgr_frame(crop)
        # Identity success is independent of expression-classification success.
        return scores
