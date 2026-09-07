import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

function getProfilePath(patientId: string) {
  return path.join(process.cwd(), "..", "data", "patients", patientId, "profile.json");
}

type RoutineActivity = {
  id: string;
  title: string;
  time: string;
  notify_before_min: number;
  grace_after_min: number;
  priority: "high" | "normal" | "low";
};

function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function toTitleCase(value: string) {
  return value
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

function normalizeTime(raw: string): string | null {
  const value = raw.trim().toLowerCase();
  const match = value.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$/i);
  if (!match) return null;

  let hour = parseInt(match[1], 10);
  const minute = match[2] ? parseInt(match[2], 10) : 0;
  const meridiem = match[3]?.toLowerCase();

  if (minute < 0 || minute > 59) return null;

  if (meridiem) {
    if (hour < 1 || hour > 12) return null;
    if (meridiem === "pm" && hour < 12) hour += 12;
    if (meridiem === "am" && hour === 12) hour = 0;
  } else {
    if (hour < 0 || hour > 23) return null;
  }

  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function parseRoutinesToActivities(routines: string): RoutineActivity[] {
  const lines = routines
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const activities: RoutineActivity[] = [];

  for (const line of lines) {
    const parts = line.split(" - ");
    if (parts.length !== 2) continue;

    const rawTime = parts[0].trim();
    const rawActivity = parts[1].trim();

    const normalizedTime = normalizeTime(rawTime);
    if (!normalizedTime || !rawActivity) continue;

    activities.push({
      id: slugify(rawActivity) || `activity_${activities.length + 1}`,
      title: toTitleCase(rawActivity),
      time: normalizedTime,
      notify_before_min: 5,
      grace_after_min: 10,
      priority: "normal",
    });
  }

  return activities;
}

export async function GET(req: NextRequest) {
  try {
    const patientId = req.nextUrl.searchParams.get("patient_id") || "P001";
    const profilePath = getProfilePath(patientId);

    if (!fs.existsSync(profilePath)) {
      return NextResponse.json({ patient_id: patientId });
    }

    const raw = fs.readFileSync(profilePath, "utf-8");
    return NextResponse.json(JSON.parse(raw));
  } catch (error) {
    console.error("Failed to load patient profile:", error);
    return NextResponse.json({ error: "Failed to load profile" }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const patientId = body.patient_id || "P001";
    const profilePath = getProfilePath(patientId);

    let existingProfile: Record<string, any> = {};
    if (fs.existsSync(profilePath)) {
      existingProfile = JSON.parse(fs.readFileSync(profilePath, "utf-8"));
    }

    const parsedActivities = parseRoutinesToActivities(body.routines || "");

    const updatedProfile = {
      ...existingProfile,
      ...body,
      patient_id: patientId,
      patient: {
        ...(existingProfile.patient || {}),
        id: patientId,
        name: body.name || body.preferred_name || existingProfile.patient?.name || "",
        preferred_name: body.preferred_name || existingProfile.patient?.preferred_name || "",
        language: body.preferred_language || existingProfile.patient?.language || "en",
        preferred_language:
          body.preferred_language || existingProfile.patient?.preferred_language || "en",
      },
      routine_template: {
        ...(existingProfile.routine_template || {}),
        activities: parsedActivities,
      },
    };

    fs.mkdirSync(path.dirname(profilePath), { recursive: true });
    fs.writeFileSync(profilePath, JSON.stringify(updatedProfile, null, 2), "utf-8");

    return NextResponse.json({
      ok: true,
      parsed_activities: parsedActivities,
    });
  } catch (error) {
    console.error("Failed to save patient profile:", error);
    return NextResponse.json({ error: "Failed to save profile" }, { status: 500 });
  }
}