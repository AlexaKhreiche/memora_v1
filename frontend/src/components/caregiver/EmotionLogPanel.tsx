"use client";

import { EmotionLogItem } from "@/types/thesis";

type Props = {
  items: EmotionLogItem[];
};

function riskClasses(risk: string) {
  switch ((risk || "").toLowerCase()) {
    case "high":
    case "critical":
      return "border-red-200 bg-red-50";
    case "medium":
      return "border-amber-200 bg-amber-50";
    default:
      return "border-emerald-200 bg-emerald-50";
  }
}

export default function EmotionLogPanel({ items }: Props) {
  return (
    <section className="rounded-[28px] border border-white/70 bg-white/85 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-6 space-y-4">
      <div>
        <div className="inline-flex rounded-full border border-violet-200 bg-violet-50 px-3 py-1 text-xs font-semibold text-violet-700">
          Emotional Signals
        </div>
        <h2 className="mt-3 text-2xl font-bold text-slate-900">Emotion Log</h2>
        <p className="mt-1 text-sm text-slate-500">
          Recent detected emotional states and associated risk context.
        </p>
      </div>

      <div className="space-y-3 max-h-72 overflow-auto pr-1">
        {items.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
            No emotion logs yet.
          </div>
        )}

        {items.map((item) => (
          <div key={item.id} className={`rounded-2xl border p-4 text-sm ${riskClasses(item.risk_level)}`}>
            <div className="flex items-center justify-between gap-3">
              <div className="font-semibold text-slate-800">
                {item.label} ({Math.round(item.confidence * 100)}%)
              </div>
              <div className="rounded-full border border-white/60 bg-white/70 px-2 py-1 text-xs font-medium text-slate-600">
                {item.risk_level}
              </div>
            </div>

            <div className="mt-2 text-slate-600">
              Risk: {Math.round(item.risk_score * 100)}%
            </div>
            <div className="text-slate-600">Source: {item.source || "unknown"}</div>
            <div className="mt-2 text-xs text-slate-400">{item.timestamp}</div>
          </div>
        ))}
      </div>
    </section>
  );
}