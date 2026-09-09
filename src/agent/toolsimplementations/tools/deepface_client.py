"""Local expression inference on OpenCV BGR camera frames."""
from math import isfinite


class DeepFaceClient:
    def __init__(self):
        # Import only in the emotion worker; other app features can start without it.
        from deepface import DeepFace

        self.analyze = DeepFace.analyze
        self.status = "ready"

    def facial_scores_from_bgr_frame(self, frame_bgr):
        try:
            faces = self.analyze(
                img_path=frame_bgr,
                actions=["emotion"],
                detector_backend="opencv",
                enforce_detection=True,
                silent=True,
            )
        except ValueError as exc:
            if "face could not be detected" in str(exc).lower():
                self.status = "no_face"
                return {}
            raise
        # Avoid attributing a bystander's expression to the patient.
        if len(faces) != 1:
            self.status = "no_face" if not faces else "multiple_faces"
            return {}
        scores = {}
        for name, value in faces[0].get("emotion", {}).items():
            score = float(value) / 100.0
            if isfinite(score) and 0 <= score <= 1:
                scores[name] = score
        self.status = "ok" if scores else "invalid_scores"
        return scores
