import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const transcript = String(body.transcript ?? "").trim();
    const patientId = String(body.patient_id ?? "P001");
    const language = String(body.language ?? "unknown");

    if (!transcript) {
      return NextResponse.json(
        { error: "Transcript is required" },
        { status: 400 }
      );
    }

    const queueDir = path.join(process.cwd(), "..", "data", "incoming_transcripts");
    fs.mkdirSync(queueDir, { recursive: true });

    const payload = {
      patient_id: patientId,
      transcript,
      confidence: 1.0,
      language,
      prosody_label: null,
      prosody_confidence: 0.0,
      created_at: new Date().toISOString(),
    };

    const filename = `msg_${Date.now()}.json`;
    const filepath = path.join(queueDir, filename);

    fs.writeFileSync(filepath, JSON.stringify(payload, null, 2), "utf-8");

    return NextResponse.json({ ok: true, queued: true, file: filename });
  } catch (error) {
    console.error("Patient message route error:", error);
    return NextResponse.json(
      { error: "Failed to queue patient message" },
      { status: 500 }
    );
  }
}