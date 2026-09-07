from __future__ import annotations

import base64
import json
import os
from typing import Dict

import websocket  # websocket-client


class HumeHTTPClient:
    """
    Hume client using STREAMING WebSocket for FACE emotion detection,
    matching your ADRD_System approach.

    Face streaming endpoint:
      wss://api.hume.ai/v0/stream/models?apikey=...

    Request payload:
      {
        "data": "<base64>",
        "models": { "face": {} }
      }

    Response payload (what we extract):
      response["face"]["predictions"][0]["emotions"]  -> list of {name, score}

    Notes:
      - This is synchronous and works well at low FPS (1–2 fps).
      - Prosody can be added later using the same streaming method.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("HUME_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Missing HUME_API_KEY in environment (.env).")

        # Exactly like your TS project:
        self.socket_url = f"wss://api.hume.ai/v0/stream/models?apikey={self.api_key}"

    # -------------------------
    # FACE (streaming) – this is the method your EmotionMonitor calls
    # -------------------------
    def facial_scores_from_bgr_frame(self, frame_bgr) -> Dict[str, float]:
        """
        OpenCV BGR frame -> JPG bytes -> base64 -> Hume face streaming -> {emotion_name: score}
        """
        import cv2

        ok, jpg = cv2.imencode(".jpg", frame_bgr)
        if not ok:
            return {}
        return self.facial_scores_from_jpg_bytes(jpg.tobytes())

    def facial_scores_from_jpg_bytes(self, jpg_bytes: bytes) -> Dict[str, float]:
        """
        JPG bytes -> Hume face streaming -> {emotion_name: score}
        """
        b64 = base64.b64encode(jpg_bytes).decode("utf-8")

        # Create a short-lived websocket connection per request (simple + reliable)
        ws = websocket.create_connection(self.socket_url, timeout=10)

        try:
            req = {
                "data": b64,
                "models": {
                    "face": {},
                },
            }
            ws.send(json.dumps(req))

            msg = ws.recv()
            resp = json.loads(msg)

            # Handle errors (Hume sometimes returns {"error": "..."} )
            if isinstance(resp, dict) and resp.get("error"):
                return {}

            # Match your TS logic:
            # const predictions = response.face?.predictions || [];
            face = resp.get("face", {}) if isinstance(resp, dict) else {}
            predictions = face.get("predictions", []) if isinstance(face, dict) else []

            if not predictions:
                return {}

            pred0 = predictions[0] if isinstance(predictions[0], dict) else {}
            emotions = pred0.get("emotions", [])

            scores: Dict[str, float] = {}
            if isinstance(emotions, list):
                for e in emotions:
                    if not isinstance(e, dict):
                        continue
                    name = e.get("name")
                    score = e.get("score")
                    if name is None or score is None:
                        continue
                    try:
                        scores[str(name)] = float(score)
                    except Exception:
                        continue

            return scores

        finally:
            try:
                ws.close()
            except Exception:
                pass

