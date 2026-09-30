from agent.runtime.model_loading import MODEL_LOAD_LOCK, prepare_cpu_model

from agent.runtime.debug_log import debug_print
"""Bounded background speech analysis and short-lived face/voice fusion."""
import base64
import queue
import subprocess
import threading
import time

MODEL = 'superb/wav2vec2-base-superb-er'
LABELS = {'neu': 'neutral', 'hap': 'happy', 'ang': 'angry', 'sad': 'sad'}


class VoiceEmotion:
    def __init__(self):
        self.jobs = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.scores = {}
        self.observed_at = 0.0
        self.running = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def submit(self, payload):
        with self.lock:
            self.scores = {}
        # Only the model's supported language; never treat missing audio as neutral.
        if payload.get('language', '').lower() not in ('en', 'english'):
            return
        audio = payload.get('audio_base64')
        if not isinstance(audio, str) or not audio or len(audio) > 8_000_000:
            return
        job = (audio, time.monotonic())
        try:
            self.jobs.put_nowait(job)
        except queue.Full:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                pass
            self.jobs.put_nowait(job)

    def fuse(self, face, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            voice = dict(self.scores) if 0 <= now - self.observed_at <= 10 else {}
        if not voice:
            return face, 'face'
        if not face:
            return voice, 'voice'
        return {key: 0.2 * face.get(key, 0) + 0.8 * voice.get(key, 0)
                for key in face.keys() | voice.keys()}, 'face+voice'

    def _loop(self):
        try:
            import numpy as np
            import torch
            import imageio_ffmpeg
            with MODEL_LOAD_LOCK:
                from transformers.models.wav2vec2.feature_extraction_wav2vec2 import Wav2Vec2FeatureExtractor
                from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2ForSequenceClassification
                extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL)
                model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL)
                prepare_cpu_model(model)
            debug_print('[VoiceEmotion] Local English speech model ready.')
        except Exception as exc:
            print(f'[VoiceEmotion] Disabled: {exc}')
            return
        while self.running:
            try:
                encoded, captured = self.jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if time.monotonic() - captured > 10:
                    continue
                raw = base64.b64decode(encoded, validate=True)
                decoded = subprocess.run(
                    [imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', 'pipe:0',
                     '-t', '15', '-f', 'f32le', '-ac', '1', '-ar', '16000', 'pipe:1'],
                    input=raw, capture_output=True, timeout=20, check=True,
                ).stdout
                audio = np.frombuffer(decoded, dtype='<f4').copy()
                if len(audio) < 16000 or not np.isfinite(audio).all() or np.sqrt(np.mean(audio ** 2)) < 0.003:
                    continue
                inputs = extractor(audio, sampling_rate=16000, return_tensors='pt', padding=True)
                with torch.inference_mode():
                    probabilities = model(**inputs).logits.softmax(dim=-1)[0].tolist()
                scores = {LABELS[model.config.id2label[i]]: float(p) for i, p in enumerate(probabilities)}
                # Do not use ambiguous voice predictions as additional evidence.
                if max(scores.values()) < 0.5:
                    continue
                with self.lock:
                    self.scores, self.observed_at = scores, captured
                debug_print(f'[VoiceEmotion] top={max(scores, key=scores.get)} score={max(scores.values()):.2f}')
            except Exception as exc:
                print(f'[VoiceEmotion] Audio analysis failed: {exc}')
