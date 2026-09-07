import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

function readJsonIfExists(filePath: string) {
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function getTodayDateKey() {
  const now = new Date();
  return now.toISOString().slice(0, 10);
}

function toMinutes(hhmm: string): number | null {
  const [h, m] = hhmm.split(":").map(Number);
  if (Number.isNaN(h) || Number.isNaN(m)) return null;
  return h * 60 + m;
}

function mergeEffectiveActivities(profile: any, daily: any) {
  const base = profile?.routine_template?.activities || [];
  let activities = base.map((activity: any) => ({ ...activity }));

  const overrides = daily?.overrides || {};
  const removeIds = new Set((overrides.remove || []).map((id: any) => String(id).trim()));

  if (removeIds.size > 0) {
    activities = activities.filter(
      (activity: any) => !removeIds.has(String(activity?.id || "").trim())
    );
  }

  const updates = overrides.update || [];
  if (Array.isArray(updates) && updates.length > 0) {
    const byId = new Map<string, any>();
    for (const activity of activities) {
      const id = String(activity?.id || "").trim();
      if (id) byId.set(id, activity);
    }

    for (const patch of updates) {
      const id = String(patch?.id || "").trim();
      if (!id || !byId.has(id)) continue;
      byId.set(id, { ...byId.get(id), ...patch });
    }

    activities = Array.from(byId.values());
  }

  const adds = overrides.add || [];
  if (Array.isArray(adds)) {
    for (const activity of adds) {
      if (activity && typeof activity === "object") {
        activities.push({ ...activity });
      }
    }
  }

  return activities;
}

function getUpcomingActivities(profile: any, daily: any) {
  const activities = mergeEffectiveActivities(profile, daily);
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const todayKey = getTodayDateKey();

  const completedIds = new Set(
    Array.isArray(daily?.completed)
      ? daily.completed.map((id: any) => String(id).trim())
      : []
  );

  const upcoming = activities
    .filter((activity: any) => activity?.time && activity?.title)
    .filter((activity: any) => !completedIds.has(String(activity?.id || "").trim()))
    .map((activity: any) => {
      const scheduledMinutes = toMinutes(activity.time);
      if (scheduledMinutes === null) return null;

      const notifyBefore = Number(activity.notify_before_min ?? 5);
      const minutesUntil = scheduledMinutes - currentMinutes;
      const isUpcoming = minutesUntil >= 0 && minutesUntil <= notifyBefore;
      const isLaterToday = minutesUntil > notifyBefore;

      return {
        id: activity.id,
        title: activity.title,
        time: activity.time,
        notify_before_min: notifyBefore,
        minutes_until: minutesUntil,
        status: isUpcoming ? "upcoming" : isLaterToday ? "later" : "passed",
        today_key: todayKey,
      };
    })
    .filter(Boolean)
    .filter(
      (activity: any) => activity.status === "upcoming" || activity.status === "later"
    )
    .sort((a: any, b: any) => a.minutes_until - b.minutes_until);

  return upcoming.slice(0, 5);
}

export async function GET() {
  try {
    const dataRoot = path.join(process.cwd(), "..", "data");
    const patientId = "P001";

    const uiPayloadPath = path.join(dataRoot, "latest_ui_payload.json");
    const profilePath = path.join(dataRoot, "patients", patientId, "profile.json");
    const dailyPath = path.join(dataRoot, "patients", patientId, "daily", `${getTodayDateKey()}.json`);

    const uiData = readJsonIfExists(uiPayloadPath) || {};
    const profile = readJsonIfExists(profilePath) || {};
    const daily = readJsonIfExists(dailyPath) || {};

    const upcomingActivities = getUpcomingActivities(profile, daily);

    return NextResponse.json({
      ...uiData,
      upcoming_activities: upcomingActivities,
      reminders_due: uiData.reminders_due || [],
      next_reminder_iso: uiData.next_reminder_iso || null,
    });
  } catch (error) {
    console.error("Failed to load caregiver state:", error);
    return NextResponse.json(
      { error: "Failed to load caregiver state" },
      { status: 500 }
    );
  }
}