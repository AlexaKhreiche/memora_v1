import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";

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

    const audioBase64 = body.audio_base64;
    if (audioBase64 != null && (typeof audioBase64 !== "string" || audioBase64.length > 8_000_000 || !/^[A-Za-z0-9+/]*={0,2}$/.test(audioBase64))) {
      return NextResponse.json({ error: "Invalid or oversized audio" }, { status: 400 });
    }
    const payload = {
      patient_id: patientId,
      transcript,
      confidence: 1.0,
      language,
      audio_base64: audioBase64 ?? null,
      created_at: new Date().toISOString(),
    };

    const filename = `msg_${Date.now()}_${randomUUID()}.json`;
    const filepath = path.join(queueDir, filename);

    fs.writeFileSync(filepath + ".tmp", JSON.stringify(payload), { encoding: "utf-8", mode: 0o600 });
    fs.renameSync(filepath + ".tmp", filepath);

    return NextResponse.json({ ok: true, queued: true, file: filename });
  } catch (error) {
    console.error("Patient message route error:", error);
    return NextResponse.json(
      { error: "Failed to queue patient message" },
      { status: 500 }
    );
  }
}