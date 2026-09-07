import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function POST(req: NextRequest) {
  try {
    const { alert_id } = await req.json();
    const jsonPath = path.join(process.cwd(), "..", "data", "latest_ui_payload.json");

    if (!fs.existsSync(jsonPath)) {
      return NextResponse.json({ ok: false, message: "No state file found" }, { status: 404 });
    }

    const raw = fs.readFileSync(jsonPath, "utf-8");
    const parsed = JSON.parse(raw);

    parsed.alerts = (parsed.alerts || []).map((alert: any) =>
      alert.id === alert_id ? { ...alert, acknowledged: true } : alert
    );

    fs.writeFileSync(jsonPath, JSON.stringify(parsed, null, 2), "utf-8");

    return NextResponse.json({ ok: true });
  } catch (error) {
    console.error("Failed to acknowledge alert:", error);
    return NextResponse.json({ error: "Failed to acknowledge alert" }, { status: 500 });
  }
}