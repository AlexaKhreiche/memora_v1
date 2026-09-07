"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MessageSquare, RotateCcw, Volume2, VolumeX } from "lucide-react";
import { ThesisUiState } from "@/types/thesis";

type Props = {
  data: ThesisUiState;
  lastUserTranscript?: string;
  onSpeakingChange?: (speaking: boolean) => void;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  language?: string;
  timestamp: string;
};

function normalizeActions(actions: string[] = []) {
  return actions.map((a) => {
    if (a === "smile") return "gentle_smile";
    if (a === "nod") return "slow_nod";
    if (a === "calm_voice") return "soft_expression";
    return a;
  });
}

function getAvatarMood(actions: string[]) {
  const normalized = normalizeActions(actions);

  if (normalized.includes("concerned_face")) return "concerned";
  if (normalized.includes("soft_expression")) return "soft";
  if (normalized.includes("gentle_smile")) return "smile";
  if (normalized.includes("listening_pose")) return "listening";
  if (normalized.includes("slow_nod")) return "calm";
  return "neutral";
}

export default function PatientAvatarExperience({
  data,
  lastUserTranscript,
  onSpeakingChange,
}: Props) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [lastReplayText, setLastReplayText] = useState("");

  const lastAssistantContentRef = useRef("");
  const lastUserContentRef = useRef("");
  const spokenContentRef = useRef("");
  const isSpeakingRef = useRef(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const normalizedActions = useMemo(
    () => normalizeActions(data.avatar_actions || []),
    [data.avatar_actions]
  );

  const mood = useMemo(() => getAvatarMood(normalizedActions), [normalizedActions]);

  useEffect(() => {
    onSpeakingChange?.(isSpeaking);
  }, [isSpeaking, onSpeakingChange]);

  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  // Stop audio when muted
  useEffect(() => {
    if (isMuted && audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
      audioRef.current = null;
      setIsSpeaking(false);
      isSpeakingRef.current = false;
    }
  }, [isMuted]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const speakWithTTS = useCallback(
    async (text: string) => {
      if (isMuted || !text.trim()) return;

      // Cancel any currently playing audio
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
        audioRef.current = null;
      }

      setIsSpeaking(true);
      isSpeakingRef.current = true;

      try {
        const voice = (data.speech_style as { tone?: string } | undefined)?.tone ?? "sage";
        const pace = data.speech_style?.pace ?? "normal";

        const res = await fetch("/api/avatar-tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, voice, pace }),
        });

        if (!res.ok) throw new Error("TTS request failed");

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audioRef.current = audio;

        audio.onended = () => {
          setIsSpeaking(false);
          isSpeakingRef.current = false;
          URL.revokeObjectURL(url);
          if (audioRef.current === audio) audioRef.current = null;
        };

        audio.onerror = () => {
          setIsSpeaking(false);
          isSpeakingRef.current = false;
          URL.revokeObjectURL(url);
          if (audioRef.current === audio) audioRef.current = null;
        };

        await audio.play();
      } catch {
        setIsSpeaking(false);
        isSpeakingRef.current = false;
      }
    },
    [isMuted, data.speech_style]
  );

  // Add user messages to chat history
  useEffect(() => {
    const transcript = (lastUserTranscript || "").trim();
    if (!transcript) return;
    if (lastUserContentRef.current === transcript) return;

    setChatHistory((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: transcript,
        language: data.response_language,
        timestamp: new Date().toISOString(),
      },
    ]);

    lastUserContentRef.current = transcript;
  }, [lastUserTranscript, data.response_language]);

  // Add assistant messages to chat history
  useEffect(() => {
    const content = (data.text_to_say || "").trim();
    if (!content) return;
    if (lastAssistantContentRef.current === content) return;

    setChatHistory((prev) => [
      ...prev,
      {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content,
        language: data.response_language,
        timestamp: data.updated_at,
      },
    ]);

    lastAssistantContentRef.current = content;
  }, [data.text_to_say, data.response_language, data.updated_at]);

  // Trigger TTS when new text arrives
  useEffect(() => {
    const content = (data.text_to_say || "").trim();
    if (!content) return;
    if (spokenContentRef.current === content) return;
    spokenContentRef.current = content;
    setLastReplayText(content);
    speakWithTTS(content);
  }, [data.text_to_say, speakWithTTS]);

  const replayLast = () => {
    if (!lastReplayText.trim()) return;
    spokenContentRef.current = "";
    speakWithTTS(lastReplayText);
  };

  const ringClass =
    mood === "concerned"
      ? "ring-4 ring-rose-200"
      : mood === "soft"
        ? "ring-4 ring-emerald-200"
        : mood === "smile"
          ? "ring-4 ring-amber-200"
          : mood === "listening"
            ? "ring-4 ring-sky-200"
            : "ring-2 ring-neutral-200";

  const statusText = isSpeaking ? "Speaking" : "Present";

  return (
    <section className="rounded-[2rem] bg-white shadow-sm border p-6 min-h-[760px] flex flex-col">
      <div className="flex items-center justify-between gap-4 mb-6">
        <div>
          <p className="text-sm text-neutral-500">Companion</p>
          <h2 className="text-2xl font-semibold">Support Avatar</h2>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsMuted((v) => !v)}
            className="p-3 rounded-xl border bg-white hover:bg-neutral-50"
            aria-label="Toggle mute"
            type="button"
          >
            {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
          </button>

          <button
            onClick={replayLast}
            className="p-3 rounded-xl border bg-white hover:bg-neutral-50"
            aria-label="Replay last response"
            type="button"
          >
            <RotateCcw className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="flex flex-col items-center">
        <div
          className={[
            "relative w-72 h-72 rounded-full bg-neutral-100 overflow-hidden transition-all duration-300",
            ringClass,
            isSpeaking ? "scale-[1.02] shadow-xl" : "scale-100 shadow-md",
          ].join(" ")}
        >
          <img
            src="/avatars/grandmother.png"
            alt="Support avatar"
            className="w-full h-full object-cover"
          />

          {isSpeaking && (
            <div className="absolute inset-0 animate-pulse bg-white/10 pointer-events-none" />
          )}

          <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
            <span className="px-4 py-2 rounded-full bg-white/90 text-sm font-medium shadow">
              {statusText}
            </span>
          </div>
        </div>

        <div className="mt-5 flex items-center gap-2 text-sm text-neutral-500">
          <MessageSquare className="w-4 h-4" />
          <span>{data.current_intervention || "conversation"}</span>
        </div>
      </div>

      <div className="mt-8 rounded-[1.5rem] bg-neutral-50 border p-5">
        <p className="text-sm text-neutral-500 mb-2">Latest reply</p>
        <p
          className={`text-2xl leading-relaxed font-medium ${
            data.response_language?.startsWith("ar") ? "text-right" : "text-left"
          }`}
          dir={data.response_language?.startsWith("ar") ? "rtl" : "ltr"}
        >
          {data.text_to_say || "No reply yet."}
        </p>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="rounded-2xl bg-neutral-50 border p-4">
          <p className="text-xs uppercase tracking-wide text-neutral-400 mb-1">Language</p>
          <p className="font-medium">{data.response_language || "en"}</p>
        </div>

        <div className="rounded-2xl bg-neutral-50 border p-4">
          <p className="text-xs uppercase tracking-wide text-neutral-400 mb-1">Emotion</p>
          <p className="font-medium">{data.stable_emotion || "unknown"}</p>
        </div>

        <div className="rounded-2xl bg-neutral-50 border p-4">
          <p className="text-xs uppercase tracking-wide text-neutral-400 mb-1">Mode</p>
          <p className="font-medium">{statusText}</p>
        </div>

        <div className="rounded-2xl bg-neutral-50 border p-4">
          <p className="text-xs uppercase tracking-wide text-neutral-400 mb-1">Risk</p>
          <p className="font-medium capitalize">{data.risk_level}</p>
        </div>
      </div>

      <div className="mt-6 flex-1 rounded-[1.5rem] border bg-white overflow-hidden flex flex-col">
        <div className="px-5 py-4 border-b bg-neutral-50">
          <h3 className="font-semibold">Conversation</h3>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4 max-h-[260px]">
          {chatHistory.length === 0 ? (
            <p className="text-sm text-neutral-400">No messages yet.</p>
          ) : (
            chatHistory.map((msg) => {
              const isArabic = (msg.language || data.response_language || "en").startsWith("ar");
              const isUser = msg.role === "user";

              return (
                <div
                  key={msg.id}
                  className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                      isUser
                        ? "bg-neutral-900 text-white"
                        : "bg-neutral-100 text-neutral-900"
                    }`}
                    dir={isArabic ? "rtl" : "ltr"}
                  >
                    {msg.content}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="mt-6">
        <p className="text-sm text-neutral-500 mb-2">Avatar actions</p>
        <div className="flex flex-wrap gap-2">
          {normalizedActions.length ? (
            normalizedActions.map((action, index) => (
              <span
                key={`${action}-${index}`}
                className="px-3 py-1 rounded-full bg-neutral-900 text-white text-sm"
              >
                {action}
              </span>
            ))
          ) : (
            <span className="text-sm text-neutral-400">No actions</span>
          )}
        </div>
      </div>
    </section>
  );
}
