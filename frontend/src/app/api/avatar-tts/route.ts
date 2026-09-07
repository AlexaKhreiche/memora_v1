import { NextResponse } from "next/server";
import OpenAI from "openai";

export const runtime = "nodejs";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const ALLOWED_VOICES = new Set([
  "alloy",
  "ash",
  "coral",
  "echo",
  "fable",
  "nova",
  "onyx",
  "sage",
  "shimmer",
]);

function normalizeVoice(input: unknown): "alloy" | "ash" | "coral" | "echo" | "fable" | "nova" | "onyx" | "sage" | "shimmer" {
  const raw = String(input ?? "").trim().toLowerCase();

  if (ALLOWED_VOICES.has(raw)) {
    return raw as "alloy" | "ash" | "coral" | "echo" | "fable" | "nova" | "onyx" | "sage" | "shimmer";
  }

  // Map your backend style hints to real OpenAI voices
  if (raw === "gentle" || raw === "warm" || raw === "calm" || raw === "soft") {
    return "sage";
  }

  if (raw === "bright" || raw === "friendly") {
    return "nova";
  }

  if (raw === "deep") {
    return "onyx";
  }

  return "sage";
}

// POST: returns full MP3 blob (used by PatientAvatarExperience for direct audio playback)
export async function POST(req: Request) {
  try {
    const body = await req.json();
    const text = String(body.text ?? "").trim();
    const voice = normalizeVoice(body.voice);
    const pace = String(body.pace ?? "normal").toLowerCase();
    const speed = pace === "slow" ? 0.85 : pace === "fast" ? 1.05 : 0.95;

    if (!text) {
      return NextResponse.json({ error: "Text is required" }, { status: 400 });
    }

    const speech = await client.audio.speech.create({
      model: "tts-1",
      voice,
      input: text,
      speed,
    });

    const buffer = Buffer.from(await speech.arrayBuffer());

    return new Response(buffer, {
      headers: {
        "Content-Type": "audio/mpeg",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("avatar-tts route error:", error);
    return NextResponse.json(
      { error: "Failed to generate avatar speech" },
      { status: 500 }
    );
  }
}

// GET: streams raw 16-bit PCM at 24kHz (used by CapstoneAvatarBridge for low-latency Simli streaming)
export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);
    const text = searchParams.get("text")?.trim() ?? "";
    const voice = normalizeVoice(searchParams.get("voice") ?? "");
    const pace = searchParams.get("pace") ?? "normal";
    const speed = pace === "slow" ? 0.85 : pace === "fast" ? 1.05 : 0.95;

    if (!text) {
      return NextResponse.json({ error: "Text is required" }, { status: 400 });
    }

    const speech = await client.audio.speech.create({
      model: "tts-1",
      voice,
      input: text,
      speed,
      response_format: "pcm", // 16-bit signed PCM at 24000 Hz, mono — no decode needed
    });

    return new Response(speech.body as ReadableStream, {
      headers: {
        "Content-Type": "audio/pcm",
        "X-Sample-Rate": "24000",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("avatar-tts GET error:", error);
    return NextResponse.json(
      { error: "Failed to generate avatar speech stream" },
      { status: 500 }
    );
  }
}