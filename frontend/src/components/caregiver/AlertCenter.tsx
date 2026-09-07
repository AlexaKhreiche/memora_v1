"use client";

import { AlertItem } from "@/types/thesis";

type Props = {
  alerts: AlertItem[];
};

function alertClasses(severity: string) {
  switch ((severity || "").toLowerCase()) {
    case "critical":
      return "border-red-200 bg-red-50";
    case "warning":
      return "border-amber-200 bg-amber-50";
    default:
      return "border-blue-200 bg-blue-50";
  }
}

function badgeClasses(severity: string) {
  switch ((severity || "").toLowerCase()) {
    case "critical":
      return "border-red-200 bg-red-100 text-red-700";
    case "warning":
      return "border-amber-200 bg-amber-100 text-amber-700";
    default:
      return "border-blue-200 bg-blue-100 text-blue-700";
  }
}

export default function AlertCenter({ alerts }: Props) {
  async function acknowledgeAlert(alertId: string) {
    try {
      await fetch("/api/acknowledge-alert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_id: alertId }),
      });
    } catch (err) {
      console.error("Failed to acknowledge alert", err);
    }
  }

  return (
    <section className="rounded-[28px] border border-white/70 bg-white/85 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-6 space-y-4">
      <div>
        <div className="inline-flex rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700">
          Notifications
        </div>
        <h2 className="mt-3 text-2xl font-bold text-slate-900">Alerts</h2>
        <p className="mt-1 text-sm text-slate-500">
          Critical and warning notifications for caregiver attention.
        </p>
      </div>

      <div className="space-y-3 max-h-[650px] overflow-auto pr-1">
        {alerts.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-5 text-sm text-slate-500">
            No alerts yet.
          </div>
        )}

        {alerts.map((alert) => (
          <div key={alert.id} className={`rounded-2xl border p-4 ${alertClasses(alert.severity)}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeClasses(alert.severity)}`}>
                    {alert.severity.toUpperCase()}
                  </span>
                  <span className="text-sm font-semibold text-slate-800">{alert.type}</span>
                </div>

                <div className="mt-2 text-sm text-slate-700">{alert.message}</div>
                <div className="mt-3 text-xs text-slate-400">{alert.timestamp}</div>
              </div>

              {!alert.acknowledged && (
                <button
                  onClick={() => acknowledgeAlert(alert.id)}
                  className="rounded-xl bg-white/80 border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-white"
                >
                  Acknowledge
                </button>
              )}
            </div>

            {alert.acknowledged && (
              <div className="mt-3 inline-flex rounded-full border border-emerald-200 bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                Acknowledged
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}