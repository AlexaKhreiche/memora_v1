"""ViT expression classification using the existing OpenCV face cropper."""
from math import isfinite
from agent.runtime.model_loading import MODEL_LOAD_LOCK, prepare_cpu_model

MODEL_ID = "dima806/facial_emotions_image_detection"


class ViTFaceClient:
    def __init__(self):
        with MODEL_LOAD_LOCK:
            from deepface import DeepFace
            from transformers.models.vit.image_processing_vit import ViTImageProcessor
            from transformers.models.vit.modeling_vit import ViTForImageClassification

            self.extract_faces = DeepFace.extract_faces
            self.processor = ViTImageProcessor.from_pretrained(MODEL_ID)
            self.model = ViTForImageClassification.from_pretrained(MODEL_ID, use_safetensors=True)
            prepare_cpu_model(self.model)
        self.status = "ready"

    def facial_scores_from_bgr_frame(self, frame_bgr):
        import torch
        try:
            faces = self.extract_faces(
                img_path=frame_bgr, detector_backend="opencv",
                enforce_detection=True, align=True,
                color_face="rgb", normalize_face=False,
            )
        except ValueError as exc:
            if "face could not be detected" in str(exc).lower():
                self.status = "no_face"
                return {}
            raise
        if len(faces) != 1:
            self.status = "no_face" if not faces else "multiple_faces"
            return {}
        # DeepFace returns an RGB crop in 0–255; the processor handles resizing
        # and the model-specific rescaling/normalization exactly once.
        inputs = self.processor(images=faces[0]["face"], return_tensors="pt")
        with torch.inference_mode():
            values = self.model(**inputs).logits.softmax(dim=-1)[0].tolist()
        scores = {self.model.config.id2label[i].lower(): float(value)
                  for i, value in enumerate(values) if isfinite(value)}
        self.status = "ok" if scores else "invalid_scores"
        return scores
