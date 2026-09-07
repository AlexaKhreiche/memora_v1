"use client";

import { ThesisUiState } from "@/types/thesis";

type Props = {
  data: ThesisUiState;
};

function riskClasses(risk: string) {
  switch ((risk || "").toLowerCase()) {
    case "high":
    case "critical":
      return "bg-red-50 border-red-200 text-red-700";
    case "medium":
      return "bg-amber-50 border-amber-200 text-amber-700";
    default:
      return "bg-emerald-50 border-emerald-200 text-emerald-700";
  }
}

export default function LiveSessionPanel({ data }: Props) {
  return (
    <section className="rounded-[28px] border border-white/70 bg-white/85 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-6 space-y-4">
      <div>
        <div className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
          Live Monitoring
        </div>
        <h2 className="mt-3 text-2xl font-bold text-slate-900">Live Session</h2>
        <p className="mt-1 text-sm text-slate-500">
          Current interaction state between the patient and avatar.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Phase</div>
          <div className="mt-2 text-sm font-semibold text-slate-800">{data.phase}</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Current Intervention</div>
          <div className="mt-2 text-sm font-semibold text-slate-800">
            {data.current_intervention || "—"}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Stable Emotion</div>
          <div className="mt-2 text-sm font-semibold text-slate-800">
            {data.stable_emotion || "—"} ({Math.round((data.stable_emotion_confidence || 0) * 100)}%)
          </div>
        </div>

        <div className={`rounded-2xl border p-4 ${riskClasses(data.risk_level)}`}>
          <div className="text-xs uppercase tracking-wide opacity-70">Risk</div>
          <div className="mt-2 text-sm font-semibold">
            {data.risk_level} ({Math.round((data.risk_score || 0) * 100)}%)
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Last Transcript</div>
        <div className="text-sm text-slate-700">{data.last_transcript || "No transcript yet."}</div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-cyan-50 to-blue-50 p-4">
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Avatar Response</div>
        <div className="text-sm text-slate-800 font-medium">{data.text_to_say || "No response yet."}</div>
      </div>

      <div className="text-xs text-slate-400">
        Last updated: {data.updated_at}
      </div>
    </section>
  );
}