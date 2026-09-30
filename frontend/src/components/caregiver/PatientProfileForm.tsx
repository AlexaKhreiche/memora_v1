"use client";

import { useEffect, useState } from "react";
import { defaultPatientProfile, PatientProfile } from "@/types/thesis";

type Props = {
  patientId: string;
};

export default function PatientProfileForm({ patientId }: Props) {
  const [form, setForm] = useState<PatientProfile>({
    ...defaultPatientProfile,
    patient_id: patientId,
  });
  const [enrolling, setEnrolling] = useState(false);
  const [identityStatus, setIdentityStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    async function loadProfile() {
      try {
        const res = await fetch(`/api/patient-profile?patient_id=${patientId}`, {
          cache: "no-store",
        });

        if (!res.ok) return;

        const json = await res.json();
        setForm({
          ...defaultPatientProfile,
          patient_id: patientId,
          ...json,
        });
      } catch (err) {
        console.error("Failed to load patient profile", err);
      }
    }

    loadProfile();
  }, [patientId]);

  async function enrollFace(photo: File) {
    setEnrolling(true);
    setIdentityStatus("Verifying reference photo… First enrollment may take a few minutes.");
    try {
      const body = new FormData();
      body.append("patient_id", patientId);
      body.append("photo", photo);
      const res = await fetch("/api/patient-face", { method: "POST", body });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error);
      setIdentityStatus("Patient reference enrolled. Facial analysis will now verify this person.");
    } catch (error) {
      setIdentityStatus(error instanceof Error ? error.message : "Enrollment failed");
    } finally { setEnrolling(false); }
  }

  function updateField<K extends keyof PatientProfile>(key: K, value: PatientProfile[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setStatus("");

    try {
      const res = await fetch("/api/patient-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        throw new Error("Failed to save profile");
      }

      setStatus("Profile saved successfully");
    } catch (err) {
      console.error(err);
      setStatus("Failed to save profile");
    } finally {
      setSaving(false);
    }
  }

  const preferencesValue =
    typeof form.preferences === "string"
      ? form.preferences
      : form.preferences
      ? JSON.stringify(form.preferences, null, 2)
      : "";

  return (
    <section className="rounded-[28px] border border-white/70 bg-white/85 backdrop-blur shadow-[0_12px_40px_rgba(15,23,42,0.08)] p-6 space-y-5">
      <div>
        <div className="inline-flex rounded-full border border-fuchsia-200 bg-fuchsia-50 px-3 py-1 text-xs font-semibold text-fuchsia-700">
          Profile Setup
        </div>
        <h2 className="mt-3 text-2xl font-bold text-slate-900">Patient Profile</h2>
        <p className="mt-1 text-sm text-slate-500">
          Add caregiver-provided details to personalize the companion experience.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 p-4 space-y-2">
        <label className="block font-medium" htmlFor="patient-face">Patient reference photo</label>
        <p className="text-sm text-slate-500">Upload one clear face (JPEG or PNG, up to 5 MB). Uploading again replaces the reference. Photo is processed locally; only its face representation is retained.</p>
        <input id="patient-face" type="file" accept="image/jpeg,image/png" disabled={enrolling}
          onChange={(e) => { const photo = e.target.files?.[0]; if (photo) void enrollFace(photo); e.target.value = ""; }} />
        <p role="status" className="text-sm">{identityStatus}</p>
      </div>
      <div className="grid grid-cols-1 gap-4">
        <input
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Patient name"
          value={form.name}
          onChange={(e) => updateField("name", e.target.value)}
        />

        <input
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Preferred name"
          value={form.preferred_name || ""}
          onChange={(e) => updateField("preferred_name", e.target.value)}
        />

        <input
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Preferred language (e.g. en, ar)"
          value={form.preferred_language || ""}
          onChange={(e) => updateField("preferred_language", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder={`Daily routines (one per line)\n09:30 - breakfast\n12:00 - lunch\n18:30 - dinner`}
          value={form.routines || ""}
          onChange={(e) => updateField("routines", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Preferences"
          value={preferencesValue}
          onChange={(e) => updateField("preferences", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Calming topics"
          value={form.calming_topics || ""}
          onChange={(e) => updateField("calming_topics", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Triggers to avoid"
          value={form.triggers_to_avoid || ""}
          onChange={(e) => updateField("triggers_to_avoid", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Mobility / fall-risk notes"
          value={form.mobility_notes || ""}
          onChange={(e) => updateField("mobility_notes", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Wandering notes"
          value={form.wandering_notes || ""}
          onChange={(e) => updateField("wandering_notes", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Medical notes"
          value={form.medical_notes || ""}
          onChange={(e) => updateField("medical_notes", e.target.value)}
        />

        <textarea
          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm min-h-[110px] outline-none transition focus:border-cyan-400 focus:ring-4 focus:ring-cyan-100"
          placeholder="Communication notes"
          value={form.communication_notes || ""}
          onChange={(e) => updateField("communication_notes", e.target.value)}
        />
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white px-5 py-3 text-sm font-semibold shadow-md transition hover:shadow-lg disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Profile"}
        </button>

        {status && (
          <span className="text-sm text-slate-600">{status}</span>
        )}
      </div>
    </section>
  );
}