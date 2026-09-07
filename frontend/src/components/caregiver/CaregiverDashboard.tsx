"use client";

import { useCaregiverState } from "@/hooks/useCaregiverState";
import PatientProfileForm from "./PatientProfileForm";
import LiveSessionPanel from "./LiveSessionPanel";
import SafetyMonitorPanel from "./SafetyMonitorPanel";
import AlertCenter from "./AlertCenter";
import EmotionLogPanel from "./EmotionLogPanel";

function getRiskBadgeClasses(risk: string) {
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

function getUpcomingBadgeClasses(status?: string) {
  switch ((status || "").toLowerCase()) {
    case "upcoming":
      return "bg-amber-100 text-amber-700 border-amber-200";
    case "due":
      return "bg-red-100 text-red-700 border-red-200";
    case "later":
      return "bg-blue-100 text-blue-700 border-blue-200";
    default:
      return "bg-slate-100 text-slate-700 border-slate-200";
  }
}

type UpcomingActivity = {
  id: string;
  title: string;
  time: string;
  notify_before_min?: number;
  minutes_until?: number;
  status?: "upcoming" | "later" | "passed" | "due";
  today_key?: string;
};

function UpcomingActivitiesPanel({
  items,
}: {
  items: UpcomingActivity[];
}) {
  return (
    <section className="rounded-[28px] border border-white/70 bg-white/80 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-5">
      <div className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
        Routine Preview
      </div>

      <h2 className="mt-3 text-2xl font-bold tracking-tight text-slate-900">
        Upcoming Activities
      </h2>

      <p className="mt-1 text-sm text-slate-500">
        Activities due soon or later today based on the patient’s saved routine.
      </p>

      <div className="mt-4 space-y-3">
        {!items?.length ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-500">
            No upcoming activities right now.
          </div>
        ) : (
          items.map((activity) => {
            const isDueNow =
              typeof activity.minutes_until === "number" &&
              activity.minutes_until <= 0;

            return (
              <div
                key={activity.id}
                className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      {activity.title}
                    </div>
                    <div className="mt-1 text-xs text-slate-600">
                      Scheduled at {activity.time}
                    </div>
                    {typeof activity.notify_before_min === "number" ? (
                      <div className="mt-1 text-[11px] text-slate-500">
                        Alert window: {activity.notify_before_min} min before
                      </div>
                    ) : null}
                  </div>

                  <div
                    className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${getUpcomingBadgeClasses(
                      isDueNow ? "due" : activity.status
                    )}`}
                  >
                    {isDueNow
                      ? "Due now"
                      : typeof activity.minutes_until === "number"
                      ? activity.minutes_until > 0
                        ? `In ${activity.minutes_until} min`
                        : activity.status || "scheduled"
                      : activity.status || "scheduled"}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

export default function CaregiverDashboard() {
  const { data, loading, error } = useCaregiverState(1000);

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50 text-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="rounded-[28px] border border-white/70 bg-white/80 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-6 md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-700">
                Caregiver View
              </div>
              <h1 className="mt-3 text-3xl md:text-4xl font-bold tracking-tight text-slate-900">
                Caregiver Dashboard
              </h1>
              <p className="mt-2 text-sm md:text-base text-slate-500 max-w-2xl">
                Monitor the live patient session, review emotional and safety
                signals, track routine activity, and manage the patient profile
                in one place.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 md:min-w-[320px]">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Patient ID
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-800">
                  {data.patient_id}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Patient Name
                </div>
                <div className="mt-1 text-sm font-semibold text-slate-800">
                  {data.patient_name || "—"}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Phase
                </div>
                <div className="mt-2 inline-flex rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
                  {data.phase}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Risk Level
                </div>
                <div
                  className={`mt-2 inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${getRiskBadgeClasses(
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
          <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 shadow-sm">
            Loading caregiver dashboard...
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_1fr_0.9fr] gap-6 items-start">
          <div className="space-y-6">
            <PatientProfileForm patientId={data.patient_id} />
          </div>

          <div className="space-y-6">
            <LiveSessionPanel data={data} />
            <SafetyMonitorPanel data={data} />
            <EmotionLogPanel items={data.emotion_log || []} />
          </div>

          <div className="space-y-6">
            <UpcomingActivitiesPanel items={data.upcoming_activities || []} />
            <AlertCenter alerts={data.alerts || []} />
          </div>
        </div>
      </div>
    </main>
  );
}