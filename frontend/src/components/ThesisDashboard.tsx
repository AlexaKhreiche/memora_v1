"use client";

import { useThesisState } from "@/hooks/useThesisState";
import CapstoneAvatarBridge from "@/components/CapstoneAvatarBridge";

function riskBadgeClasses(risk: string) {
  switch ((risk || "").toLowerCase()) {
    case "high":
    case "critical":
      return "bg-red-100 text-red-700 border-red-200";
    case "medium":
      return "bg-amber-100 text-amber-700 border-amber-200";
    default:
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
  }
}

function phaseBadgeClasses(phase: string) {
  switch ((phase || "").toUpperCase()) {
    case "PROCESSING":
      return "bg-blue-100 text-blue-700 border-blue-200";
    case "BOOT":
      return "bg-violet-100 text-violet-700 border-violet-200";
    default:
      return "bg-cyan-100 text-cyan-700 border-cyan-200";
  }
}

export default function ThesisDashboard() {
  const { data, loading, error } = useThesisState(300);

  return (
    <main className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-cyan-50 text-slate-900 p-4 md:p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="rounded-[32px] border border-white/70 bg-white/85 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-6 md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="inline-flex rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-700">
                Companion Session
              </div>

              <h1 className="mt-3 text-3xl md:text-4xl font-bold tracking-tight text-slate-900">
                Hello{data.patient_name ? `, ${data.patient_name}` : ""}
              </h1>

              <p className="mt-2 max-w-2xl text-sm md:text-base text-slate-500 leading-relaxed">
                Your companion is here to listen, talk with you, and support you through the session.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 min-w-full lg:min-w-[420px]">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Patient
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-800">
                  {data.patient_name || data.patient_id}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Phase
                </div>
                <div
                  className={`mt-2 inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${phaseBadgeClasses(
                    data.phase
                  )}`}
                >
                  {data.phase}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Risk
                </div>
                <div
                  className={`mt-2 inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${riskBadgeClasses(
                    data.risk_level
                  )}`}
                >
                  {data.risk_level} ({Math.round((data.risk_score || 0) * 100)}%)
                </div>
              </div>
            </div>
          </div>
        </header>

        {loading && (
          <div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 text-blue-800 shadow-sm">
            Loading session...
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 shadow-sm">
            {error}
          </div>
        )}

        <section className="rounded-[32px] border border-white/70 bg-white/60 backdrop-blur-sm p-2 md:p-3 shadow-[0_12px_40px_rgba(15,23,42,0.05)]">
          <CapstoneAvatarBridge data={data} />
        </section>
      </div>
    </main>
  );
}