import { NextResponse } from "next/server";
import OpenAI from "openai";
import fs from "fs";
import os from "os";
import path from "path";

export const runtime = "nodejs";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function POST(req: Request) {
  let tempPath: string | null = null;
  try {
    const formData = await req.formData();
    const audio = formData.get("audio");

    if (!(audio instanceof File)) {
      return NextResponse.json({ error: "No audio file provided" }, { status: 400 });
    }

    const bytes = Buffer.from(await audio.arrayBuffer());
    tempPath = path.join(os.tmpdir(), `speech-${Date.now()}.webm`);
    await fs.promises.writeFile(tempPath, bytes);

    const transcription = await client.audio.transcriptions.create({
      file: fs.createReadStream(tempPath),
      model: "whisper-1",
      response_format: "verbose_json",
    });

    const noSpeechProb: number =
      Array.isArray((transcription as any).segments) && (transcription as any).segments.length > 0
        ? (transcription as any).segments[0].no_speech_prob ?? 0
        : 0;

    return NextResponse.json({
      text: transcription.text ?? "",
      language: transcription.language ?? "unknown",
      no_speech_prob: noSpeechProb,
    });
  } catch (error) {
    console.error("Whisper route error:", error);
    return NextResponse.json(
      { error: "Failed to transcribe audio" },
      { status: 500 }
    );
  } finally {
    if (tempPath) {
      fs.promises.unlink(tempPath).catch(() => {});
    }
  }
}