import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import os from "os";
import { execFile } from "child_process";
import { promisify } from "util";
export const runtime = "nodejs";
export const maxDuration = 180;
const execute = promisify(execFile);

export async function POST(req: Request) {
  let temporary: string | undefined;
  try {
    const form = await req.formData();
    const id = String(form.get("patient_id") || "");
    const photo = form.get("photo");
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(id) || !(photo instanceof File) ||
        !["image/jpeg", "image/png"].includes(photo.type) || photo.size > 5_000_000 || !photo.size) {
      return NextResponse.json({ error: "Choose a JPEG or PNG under 5 MB and a valid patient." }, { status: 400 });
    }
    const root = path.resolve(process.cwd(), "..");
    temporary = await fs.mkdtemp(path.join(os.tmpdir(), "memora-enroll-"));
    const input = path.join(temporary, "reference");
    await fs.writeFile(input, Buffer.from(await photo.arrayBuffer()), { mode: 0o600 });
    await execute(path.join(root, ".venv/bin/python"),
      [path.join(root, "src/scripts/enroll_patient_face.py"), id, input],
      { cwd: root, timeout: 170000, maxBuffer: 2_000_000 });
    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ error: "Enrollment failed. Use a clear photo with exactly one face. The first enrollment also needs internet access to download the identity model." }, { status: 422 });
  } finally {
    if (temporary) await fs.rm(temporary, { recursive: true, force: true });
  }
}
