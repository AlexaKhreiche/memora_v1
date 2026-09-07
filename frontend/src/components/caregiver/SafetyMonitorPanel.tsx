"use client";

import { ThesisUiState } from "@/types/thesis";

type Props = {
  data: ThesisUiState;
};

export default function SafetyMonitorPanel({ data }: Props) {
  return (
    <section className="rounded-[28px] border border-white/70 bg-white/85 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-6 space-y-4">
      <div>
        <div className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700">
          Safety Tracking
        </div>
        <h2 className="mt-3 text-2xl font-bold text-slate-900">Safety Monitor</h2>
        <p className="mt-1 text-sm text-slate-500">
          Fall detection and wandering / presence tracking.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3">
        <div
          className={`rounded-2xl border p-4 ${
            data.fall_active
              ? "border-red-200 bg-red-50"
              : "border-emerald-200 bg-emerald-50"
          }`}
        >
          <div className="text-xs uppercase tracking-wide text-slate-400">Fall Status</div>
          <div className={`mt-2 text-sm font-semibold ${data.fall_active ? "text-red-700" : "text-emerald-700"}`}>
            {data.fall_active ? "Possible fall detected" : "No fall currently detected"}
          </div>
        </div>

        <div
          className={`rounded-2xl border p-4 ${
            data.wandering_active
              ? "border-amber-200 bg-amber-50"
              : "border-cyan-200 bg-cyan-50"
          }`}
        >
          <div className="text-xs uppercase tracking-wide text-slate-400">Wandering / Presence</div>
          <div className={`mt-2 text-sm font-semibold ${data.wandering_active ? "text-amber-700" : "text-cyan-700"}`}>
            {data.wandering_active
              ? "Patient may be out of frame / wandering"
              : "Patient currently in frame"}
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <div className="text-sm font-semibold text-slate-800">Recent Safety Events</div>

        <div className="space-y-2 max-h-60 overflow-auto pr-1">
          {(data.safety_log || []).length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
              No safety events yet.
            </div>
          )}

          {(data.safety_log || []).map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm">
              <div className="font-semibold text-slate-800">
                {item.type.toUpperCase()} — {item.active ? "ACTIVE" : "CLEAR"}
              </div>
              <div className="mt-1 text-slate-600">
                Confidence: {Math.round(item.confidence * 100)}%
              </div>
              {!!item.reasons?.length && (
                <div className="mt-1 text-slate-600">Reasons: {item.reasons.join(", ")}</div>
              )}
              <div className="mt-2 text-xs text-slate-400">{item.timestamp}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}