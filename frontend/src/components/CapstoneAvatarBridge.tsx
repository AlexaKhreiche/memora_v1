"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Loader2,
  Phone,
  PhoneOff,
  Volume2,
  VolumeX,
  MessageSquare,
} from "lucide-react";
import {
  generateSimliSessionToken,
  SimliClient,
  SimliSessionRequest,
  generateIceServers,
  LogLevel,
} from "simli-client";
import { ThesisUiState } from "@/types/thesis";

type Props = {
  data: ThesisUiState;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
};

type ConnectionState = "disconnected" | "connecting" | "connected" | "error";

const SIMLI_FACE_ID = "0c2b8b04-5274-41f1-a21c-d5c98322efa9";

function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

function similarityRatio(a: string, b: string): number {
  const aa = normalizeText(a);
  const bb = normalizeText(b);

  if (!aa || !bb) return 0;
  if (aa === bb) return 1;

  const aWords = new Set(aa.split(" "));
  const bWords = new Set(bb.split(" "));
  let overlap = 0;

  for (const word of aWords) {
    if (bWords.has(word)) overlap += 1;
  }

  return overlap / Math.max(aWords.size, bWords.size, 1);
}

function isLikelyEcho(transcript: string, assistantText: string): boolean {
  const t = normalizeText(transcript);
  const a = normalizeText(assistantText);

  if (!t || !a) return false;
  if (similarityRatio(t, a) >= 0.45) return true;
  if (t.length >= 12 && a.includes(t)) return true;
  if (a.length >= 12 && t.includes(a)) return true;

  return false;
}


function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function CapstoneAvatarBridge({ data }: Props) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState("Disconnected");
  const [isMuted, setIsMuted] = useState(false);
  const [sessionActive, setSessionActive] = useState(false);
  const [isRecordingUtterance, setIsRecordingUtterance] = useState(false);
  const [isAvatarSpeaking, setIsAvatarSpeaking] = useState(false);
  const [lastTranscript, setLastTranscript] = useState("");
  const [lastLanguage, setLastLanguage] = useState("unknown");
  const [volumeLevel, setVolumeLevel] = useState(0);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const simliRef = useRef<SimliClient | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const monitorIntervalRef = useRef<number | null>(null);

  const chunksRef = useRef<Blob[]>([]);
  const silenceStartRef = useRef<number | null>(null);
  const sessionActiveRef = useRef(false);
  const isRecordingUtteranceRef = useRef(false);
  const isUploadingRef = useRef(false);
  const isAvatarSpeakingRef = useRef(false);
  const avatarBlockUntilRef = useRef(0);

  const lastSubmittedTranscriptRef = useRef("");
  const lastSpokenBackendTextRef = useRef("");
  const isPlayingBackendSpeechRef = useRef(false);
  const ttsAbortRef = useRef<AbortController | null>(null);

  const START_THRESHOLD = 4;
  const SILENCE_MS = 500;
  const MONITOR_EVERY_MS = 60;
  const AVATAR_COOLDOWN_MS = 700;

  useEffect(() => {
    sessionActiveRef.current = sessionActive;
  }, [sessionActive]);

  useEffect(() => {
    isRecordingUtteranceRef.current = isRecordingUtterance;
  }, [isRecordingUtterance]);

  useEffect(() => {
    isAvatarSpeakingRef.current = isAvatarSpeaking;
  }, [isAvatarSpeaking]);

  useEffect(() => {
    return () => {
      cleanupAudioMonitoring();
      void stopAvatarSession();
    };
  }, []);

  useEffect(() => {
    const transcript = (lastTranscript || "").trim();
    if (!transcript) return;

    setChatHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === "user" && last.content === transcript) return prev;
      return [
        ...prev,
        {
          id: `user-${Date.now()}`,
          role: "user",
          content: transcript,
          timestamp: new Date().toISOString(),
        },
      ];
    });
  }, [lastTranscript]);

  useEffect(() => {
    const text = (data.text_to_say || "").trim();
    if (!text) return;
    if (connectionState !== "connected") return;
    if (isPlayingBackendSpeechRef.current) return;
    if (lastSpokenBackendTextRef.current === text) return;

    lastSpokenBackendTextRef.current = text;

    setChatHistory((prev) => {
      const last = prev[prev.length - 1];
      if (last?.role === "assistant" && last.content === text) return prev;
      return [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: text,
          timestamp: new Date().toISOString(),
        },
      ];
    });

    void speakBackendText(text);
  }, [data.text_to_say, connectionState]);

  const cleanupAudioMonitoring = useCallback(() => {
    if (monitorIntervalRef.current) {
      window.clearInterval(monitorIntervalRef.current);
      monitorIntervalRef.current = null;
    }

    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      try {
        recorderRef.current.stop();
      } catch {}
    }
    recorderRef.current = null;

    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch {}
      sourceRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    analyserRef.current = null;
    silenceStartRef.current = null;
    chunksRef.current = [];
    setIsRecordingUtterance(false);
    setVolumeLevel(0);
  }, []);

  const transcribeAndQueue = useCallback(
    async (blob: Blob) => {
      if (isUploadingRef.current) return;

      try {
        isUploadingRef.current = true;
        setStatus("Transcribing...");

        const formData = new FormData();
        formData.append("audio", blob, "utterance.webm");

        const whisperRes = await fetch("/api/whisper", {
          method: "POST",
          body: formData,
        });

        const whisperJson = await whisperRes.json();

        if (!whisperRes.ok) {
          throw new Error(whisperJson?.error || "Whisper transcription failed");
        }

        const transcript = String(whisperJson?.text ?? "").trim();
        const language = String(whisperJson?.language ?? "unknown");

        setLastLanguage(language);

        if (!transcript) {
          setStatus("Listening...");
          return;
        }

        const currentAssistantText = (data.text_to_say || "").trim();

        if (
          isLikelyEcho(transcript, currentAssistantText) ||
          isLikelyEcho(transcript, lastSpokenBackendTextRef.current)
        ) {
          setStatus("Ignoring avatar echo...");
          avatarBlockUntilRef.current = Date.now() + AVATAR_COOLDOWN_MS;
          return;
        }

        if (lastSubmittedTranscriptRef.current === transcript) {
          setStatus("Duplicate transcript ignored");
          return;
        }

        lastSubmittedTranscriptRef.current = transcript;
        setLastTranscript(transcript);
        setStatus("Sending to Capstone brain...");

        const queueRes = await fetch("/api/patient-message", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            patient_id: data.patient_id,
            transcript,
            language,
          }),
        });

        const queueJson = await queueRes.json();

        if (!queueRes.ok) {
          throw new Error(queueJson?.error || "Failed to queue patient message");
        }

        avatarBlockUntilRef.current = Date.now() + 250;
        setStatus("Listening...");
      } catch (err) {
        console.error(err);
        setStatus("Transcription failed");
      } finally {
        isUploadingRef.current = false;
      }
    },
    [data.patient_id, data.text_to_say]
  );

  const stopCurrentUtteranceRecording = useCallback(
    (shouldProcess: boolean) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") return;

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        chunksRef.current = [];
        setIsRecordingUtterance(false);

        if (shouldProcess && blob.size > 0) {
          await transcribeAndQueue(blob);
        } else {
          setStatus(sessionActiveRef.current ? "Listening..." : "Stopped");
        }
      };

      try {
        recorder.stop();
      } catch {
        setIsRecordingUtterance(false);
      }
    },
    [transcribeAndQueue]
  );

  const startUtteranceRecording = useCallback(() => {
    if (!streamRef.current) return;
    if (recorderRef.current && recorderRef.current.state === "recording") return;

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    chunksRef.current = [];
    const recorder = new MediaRecorder(streamRef.current, { mimeType });
    recorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };

    recorder.onstart = () => {
      setIsRecordingUtterance(true);
      setStatus("Recording patient speech...");
    };

    recorder.start();
  }, []);

  const beginMonitoring = useCallback(() => {
    if (!analyserRef.current) return;

    const analyser = analyserRef.current;
    const dataArray = new Uint8Array(analyser.fftSize);

    monitorIntervalRef.current = window.setInterval(() => {
      if (!sessionActiveRef.current) return;
      if (isAvatarSpeakingRef.current) return;
      if (isUploadingRef.current) return;

      const now = Date.now();

      if (now < avatarBlockUntilRef.current) {
        setVolumeLevel(0);
        setStatus("Waiting for avatar audio to clear...");
        return;
      }

      analyser.getByteTimeDomainData(dataArray);

      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += Math.abs(dataArray[i] - 128);
      }

      const averageAmplitude = sum / dataArray.length;
      setVolumeLevel(Math.min(100, Math.round(averageAmplitude * 4)));

      if (averageAmplitude > START_THRESHOLD) {
        silenceStartRef.current = null;

        if (!isRecordingUtteranceRef.current) {
          startUtteranceRecording();
        }
      } else if (isRecordingUtteranceRef.current) {
        if (silenceStartRef.current === null) {
          silenceStartRef.current = now;
        } else if (now - silenceStartRef.current >= SILENCE_MS) {
          silenceStartRef.current = null;
          stopCurrentUtteranceRecording(true);
        }
      } else {
        setStatus("Listening...");
      }
    }, MONITOR_EVERY_MS);
  }, [startUtteranceRecording, stopCurrentUtteranceRecording]);

  const startAudioMonitoring = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    streamRef.current = stream;

    const AudioContextClass =
      window.AudioContext ||
      (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

    if (!AudioContextClass) {
      throw new Error("AudioContext is not supported in this browser");
    }

    const audioContext = new AudioContextClass();
    await audioContext.resume();

    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.8;

    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    audioContextRef.current = audioContext;
    analyserRef.current = analyser;
    sourceRef.current = source;

    avatarBlockUntilRef.current = Date.now() + 1500;
    setSessionActive(true);
    sessionActiveRef.current = true;
    setStatus("Listening...");
    beginMonitoring();
  }, [beginMonitoring]);

  const initializeSimliClient = useCallback(async () => {
    if (!videoRef.current || !audioRef.current) {
      throw new Error("Avatar media elements are not ready");
    }

    const apiKey = process.env.NEXT_PUBLIC_SIMLI_API_KEY;
    if (!apiKey) {
      throw new Error("NEXT_PUBLIC_SIMLI_API_KEY is missing");
    }

    const config: SimliSessionRequest = {
      faceId: SIMLI_FACE_ID,
      handleSilence: true,
      maxSessionLength: 6000,
      maxIdleTime: 6000,
      model: "fasttalk",
    };

    const sessionToken = await generateSimliSessionToken({ apiKey, config });
    const iceServers = await generateIceServers(apiKey);

    const client = new SimliClient(
      sessionToken.session_token,
      videoRef.current,
      audioRef.current,
      iceServers,
      LogLevel.DEBUG,
      "p2p"
    );

    client.on("start", () => {
      setConnectionState("connected");
      setStatus("Avatar connected");
    });

    client.on("speaking", () => {
      setIsAvatarSpeaking(true);
      isAvatarSpeakingRef.current = true;
    });

    client.on("silent", () => {
      setIsAvatarSpeaking(false);
      isAvatarSpeakingRef.current = false;
      avatarBlockUntilRef.current = Date.now() + AVATAR_COOLDOWN_MS;
    });

    client.on("stop", () => {
      setConnectionState("disconnected");
      setIsAvatarSpeaking(false);
      isAvatarSpeakingRef.current = false;
      setStatus("Avatar disconnected");
    });

    client.on("error", (err: unknown) => {
      console.error("Simli error:", err);
      setConnectionState("error");
      setError("Avatar connection error");
      setStatus("Avatar error");
    });

    simliRef.current = client;
    await client.start();
  }, []);

  const startAvatarSession = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      setConnectionState("connecting");
      setStatus("Connecting avatar...");

      await initializeSimliClient();
      await startAudioMonitoring();
    } catch (err) {
      console.error(err);
      setConnectionState("error");
      setError(err instanceof Error ? err.message : "Failed to start avatar session");
      setStatus("Failed to start");
    } finally {
      setIsLoading(false);
    }
  }, [initializeSimliClient, startAudioMonitoring]);

  const stopAvatarSession = useCallback(async () => {
    cleanupAudioMonitoring();
    sessionActiveRef.current = false;
    setSessionActive(false);
    setIsAvatarSpeaking(false);
    isAvatarSpeakingRef.current = false;
    setStatus("Stopped");

    if (simliRef.current) {
      try {
        await simliRef.current.stop();
      } catch {}
      simliRef.current = null;
    }

    setConnectionState("disconnected");
  }, [cleanupAudioMonitoring]);

  const toggleMute = useCallback(() => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted((prev) => !prev);
  }, [isMuted]);

  const speakBackendText = useCallback(
    async (text: string) => {
      if (!simliRef.current) return;
      if (!text.trim()) return;

      // Abort any in-flight stream before starting a new one
      ttsAbortRef.current?.abort();
      const abort = new AbortController();
      ttsAbortRef.current = abort;

      try {
        isPlayingBackendSpeechRef.current = true;
        setStatus("Avatar responding...");
        setIsAvatarSpeaking(true);
        isAvatarSpeakingRef.current = true;
        avatarBlockUntilRef.current = Date.now() + 60_000;

        stopCurrentUtteranceRecording(false);

        // Stream raw PCM (16-bit signed, 24000 Hz, mono) — no decode step needed,
        // and first chunks arrive ~100ms faster than waiting for a full MP3 buffer.
        const params = new URLSearchParams({ text, voice: "sage", pace: "normal" });
        const ttsRes = await fetch(`/api/avatar-tts?${params.toString()}`, {
          signal: abort.signal,
        });

        if (!ttsRes.ok || !ttsRes.body) throw new Error("TTS stream failed");

        // OpenAI PCM: 16-bit signed int, 24000 Hz, mono
        const INPUT_RATE = 24000;
        const OUTPUT_RATE = 16000;
        const OUTPUT_CHUNK_SAMPLES = 320; // 20 ms at 16 kHz
        const INPUT_CHUNK_SAMPLES = Math.ceil(OUTPUT_CHUNK_SAMPLES * INPUT_RATE / OUTPUT_RATE); // 480
        const INPUT_CHUNK_BYTES = INPUT_CHUNK_SAMPLES * 2; // 960 bytes

        // Downsample Int16 array directly — no float32 round-trip needed
        const downsampleInt16 = (src: Int16Array): Int16Array => {
          const out = new Int16Array(OUTPUT_CHUNK_SAMPLES);
          const ratio = INPUT_RATE / OUTPUT_RATE;
          for (let i = 0; i < OUTPUT_CHUNK_SAMPLES; i++) {
            const s = i * ratio;
            const lo = Math.floor(s);
            const hi = Math.min(lo + 1, src.length - 1);
            out[i] = Math.round(src[lo] * (1 - (s - lo)) + src[hi] * (s - lo));
          }
          return out;
        };

        const reader = ttsRes.body.getReader();
        let pending = new Uint8Array(0);
        const startTime = performance.now();
        let chunksSent = 0;

        while (true) {
          const { done, value } = await reader.read();
          if (abort.signal.aborted) break;

          if (value) {
            const merged = new Uint8Array(pending.length + value.length);
            merged.set(pending);
            merged.set(value, pending.length);
            pending = merged;
          }

          // Send all complete 960-byte chunks immediately as they arrive
          while (pending.length >= INPUT_CHUNK_BYTES) {
            if (abort.signal.aborted || !simliRef.current) break;

            const chunkBytes = pending.slice(0, INPUT_CHUNK_BYTES);
            pending = pending.slice(INPUT_CHUNK_BYTES);

            // Drift-corrected pacing: compensates for setTimeout imprecision
            chunksSent++;
            const elapsed = performance.now() - startTime;
            const delay = Math.max(0, chunksSent * 20 - elapsed);
            if (delay > 0) await sleep(delay);

            if (abort.signal.aborted || !simliRef.current) break;
            const pcm = downsampleInt16(new Int16Array(chunkBytes.buffer, chunkBytes.byteOffset, INPUT_CHUNK_SAMPLES));
            simliRef.current.sendAudioData(pcm as never);
          }

          if (done) {
            // Flush any remaining bytes (< one full chunk) padded with silence
            if (pending.length >= 2 && !abort.signal.aborted && simliRef.current) {
              const padded = new Uint8Array(INPUT_CHUNK_BYTES);
              padded.set(pending.slice(0, Math.min(pending.length, INPUT_CHUNK_BYTES)));
              const pcm = downsampleInt16(new Int16Array(padded.buffer));
              simliRef.current.sendAudioData(pcm as never);
            }
            break;
          }
        }

        if (!abort.signal.aborted) {
          avatarBlockUntilRef.current = Date.now() + AVATAR_COOLDOWN_MS;
          setStatus("Listening...");
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        console.error("speakBackendText error:", err);
        setStatus("Avatar speech failed");
      } finally {
        if (!abort.signal.aborted) {
          isPlayingBackendSpeechRef.current = false;
          setIsAvatarSpeaking(false);
          isAvatarSpeakingRef.current = false;
          avatarBlockUntilRef.current = Date.now() + AVATAR_COOLDOWN_MS;
        }
      }
    },
    [stopCurrentUtteranceRecording]
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] bg-white border shadow-sm p-5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-xl font-semibold">Live Avatar</h2>
            <p className="text-sm text-neutral-500">Avatar conversation interface</p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleMute}
              className="rounded-xl border px-3 py-2 text-sm hover:bg-neutral-50"
              type="button"
            >
              {isMuted ? (
                <span className="inline-flex items-center gap-2">
                  <VolumeX className="w-4 h-4" />
                  Muted
                </span>
              ) : (
                <span className="inline-flex items-center gap-2">
                  <Volume2 className="w-4 h-4" />
                  Audio
                </span>
              )}
            </button>

            {connectionState === "connected" ? (
              <button
                onClick={() => void stopAvatarSession()}
                className="rounded-xl bg-red-600 text-white px-4 py-2 text-sm hover:bg-red-700"
                type="button"
              >
                <span className="inline-flex items-center gap-2">
                  <PhoneOff className="w-4 h-4" />
                  Stop
                </span>
              </button>
            ) : (
              <button
                onClick={() => void startAvatarSession()}
                disabled={isLoading}
                className="rounded-xl bg-neutral-900 text-white px-4 py-2 text-sm hover:bg-neutral-800 disabled:opacity-60"
                type="button"
              >
                <span className="inline-flex items-center gap-2">
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Phone className="w-4 h-4" />
                  )}
                  Start
                </span>
              </button>
            )}
          </div>
        </div>

        <div className="rounded-[1.5rem] overflow-hidden bg-neutral-950 relative border min-h-[520px] xl:min-h-[620px]">
          <video ref={videoRef} autoPlay playsInline className="w-full h-full object-cover" />
          <audio ref={audioRef} autoPlay playsInline muted={isMuted} />

          <div className="absolute left-4 top-4 flex flex-wrap gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs border ${
                connectionState === "connected"
                  ? "bg-emerald-100 text-emerald-700 border-emerald-200"
                  : connectionState === "connecting"
                  ? "bg-blue-100 text-blue-700 border-blue-200"
                  : connectionState === "error"
                  ? "bg-red-100 text-red-700 border-red-200"
                  : "bg-neutral-100 text-neutral-700 border-neutral-200"
              }`}
            >
              {connectionState}
            </span>

            {isAvatarSpeaking && (
              <span className="rounded-full px-3 py-1 text-xs border bg-purple-100 text-purple-700 border-purple-200">
                avatar speaking
              </span>
            )}

            {isRecordingUtterance && (
              <span className="rounded-full px-3 py-1 text-xs border bg-amber-100 text-amber-700 border-amber-200">
                recording patient
              </span>
            )}
          </div>

          <div className="absolute bottom-4 left-4 right-4 rounded-2xl bg-black/55 text-white p-3 backdrop-blur-sm">
            <div className="text-sm font-medium">{status}</div>
            <div className="mt-2 h-2 w-full rounded-full bg-white/15 overflow-hidden">
              <div
                className="h-full rounded-full bg-white transition-all"
                style={{ width: `${volumeLevel}%` }}
              />
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 text-sm">
            {error}
          </div>
        )}
      </section>

      <div className="rounded-[2rem] bg-white border shadow-sm p-5">
        <div className="flex items-center gap-2 mb-3">
          <MessageSquare className="w-5 h-5 text-neutral-700" />
          <h3 className="text-lg font-semibold">Conversation</h3>
        </div>

        <div className="max-h-[380px] overflow-y-auto space-y-3">
          {chatHistory.length === 0 ? (
            <div className="rounded-2xl border border-dashed p-4 text-sm text-neutral-500">
              No conversation yet.
            </div>
          ) : (
            chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`rounded-2xl p-3 text-sm ${
                  msg.role === "assistant"
                    ? "bg-neutral-100 border border-neutral-200"
                    : "bg-blue-50 border border-blue-200"
                }`}
              >
                <div className="text-xs uppercase tracking-wide text-neutral-500 mb-1">
                  {msg.role === "assistant" ? "avatar" : "patient"}
                </div>
                <div>{msg.content}</div>
              </div>
            ))
          )}
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="rounded-2xl border p-3 text-sm">
            <div className="text-neutral-500 mb-1">Last patient transcript</div>
            <div className="font-medium">{lastTranscript || "—"}</div>
            <div className="text-xs text-neutral-400 mt-1">language: {lastLanguage}</div>
          </div>

          <div className="rounded-2xl border p-3 text-sm">
            <div className="text-neutral-500 mb-1">Current avatar reply</div>
            <div className="font-medium">{data.text_to_say || "—"}</div>
          </div>
        </div>
      </div>
    </div>
  );
}