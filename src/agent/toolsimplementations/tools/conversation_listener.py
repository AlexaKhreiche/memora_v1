from __future__ import annotations

import io
import wave
import numpy as np
import sounddevice as sd
from openai import OpenAI
from dotenv import load_dotenv

from models.tools_schemas.transcript_report import TranscriptReport

load_dotenv()


class ConversationListener:
    """
    Records audio from the microphone and sends it to OpenAI Whisper for transcription.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        silence_threshold: float = 0.0002,
        silence_duration_s: float = 1.0,
        max_duration_s: float = 15.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration_s = silence_duration_s
        self.max_duration_s = max_duration_s
        self.client = OpenAI()

    def _record_until_silence(self) -> np.ndarray:
        """
        Record from mic until:
          - patient stops talking (silence_duration_s of quiet), OR
          - max_duration_s reached
        """
        chunk_duration = 0.1  # 100ms
        chunk_samples = int(self.sample_rate * chunk_duration)
        max_chunks = int(self.max_duration_s / chunk_duration)
        silence_chunks_needed = int(self.silence_duration_s / chunk_duration)

        frames = []
        silent_chunks = 0
        started_speaking = False

        for _ in range(max_chunks):
            chunk = sd.rec(
                chunk_samples,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
            )
            sd.wait()

            volume = float(np.abs(chunk).mean())
            frames.append(chunk)

            if volume > self.silence_threshold:
                started_speaking = True
                silent_chunks = 0
            else:
                silent_chunks += 1

            if started_speaking and silent_chunks >= silence_chunks_needed:
                break

        return np.concatenate(frames, axis=0) if frames else np.zeros((0, 1), dtype=np.float32)

    def _audio_to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Convert float32 numpy array to WAV bytes (16-bit PCM)."""
        if audio.size == 0:
            return b""

        audio_int16 = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()

    def listen(self) -> TranscriptReport:
        print("[MIC] Listening...")
        audio = self._record_until_silence()

        # If we got mostly silence, return empty
        if audio.size == 0 or float(np.abs(audio).mean()) < self.silence_threshold * 0.5:
            print("[MIC] No speech detected.")
            return TranscriptReport(transcript="", confidence=0.0, language=None)

        print("[MIC] Sending to Whisper API...")
        wav_bytes = self._audio_to_wav_bytes(audio)

        # -------------------------
        # Whisper transcription
        # -------------------------
        result = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_bytes, "audio/wav"),
            response_format="verbose_json",
        )

        text = result.text.strip() if getattr(result, "text", None) else ""
        language = getattr(result, "language", None)

        # Whisper doesn’t give a single “confidence” field.
        # Use exp(avg_logprob) from segments as a proxy when available.
        confidence = 1.0
        segments = getattr(result, "segments", None)
        if segments:
            logprobs = []
            for s in segments:
                if isinstance(s, dict):
                    logprobs.append(float(s.get("avg_logprob", 0.0)))
                else:
                    logprobs.append(float(getattr(s, "avg_logprob", 0.0)))
            if logprobs:
                import math
                avg_logprob = sum(logprobs) / len(logprobs)
                confidence = min(max(math.exp(avg_logprob), 0.0), 1.0)

        print(f'[MIC] Transcript: "{text}" (conf={confidence:.2f}, lang={language})')

        return TranscriptReport(
            transcript=text,
            confidence=confidence,
            language=language,
        )


if __name__ == "__main__":
    listener = ConversationListener(silence_threshold=0.003)
    report = listener.listen()
    print("Result:", report)