import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const fallbackState = {
  patient_id: "P001",
  phase: "WAITING",
  stable_emotion: null,
  stable_emotion_confidence: 0,
  current_intervention: null,
  text_to_say: "",
  avatar_actions: [],
  fall_active: false,
  wandering_active: false,
  caregiver_alert_sent: false,
  risk_level: "low",
  risk_score: 0,
  updated_at: new Date().toISOString(),
};

export async function GET() {
  try {
    const jsonPath = path.join(
      process.cwd(),
      "..",
      "data",
      "latest_ui_payload.json"
    );

    if (!fs.existsSync(jsonPath)) {
      return NextResponse.json(fallbackState);
    }

    const raw = fs.readFileSync(jsonPath, "utf-8");
    const parsed = JSON.parse(raw);

    return NextResponse.json(parsed);
  } catch (error) {
    console.error("Failed to read UI payload:", error);
    return NextResponse.json(fallbackState);
  }
}