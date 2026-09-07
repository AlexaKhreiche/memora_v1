from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict


EMOJIS = {
    "brain": "🧠",
    "event": "📨",
    "emotion": "😊",
    "fall": "🚨",
    "wander": "🚶",
    "timer": "⏰",
    "ui": "🖥️",
    "latency": "⚡",
    "mic": "🎤",
    "tts": "🗣️",
    "state": "📌",
    "warn": "⚠️",
    "error": "❌",
    "ok": "✅",
    "debug": "🔍",
}


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _pretty(data: Any) -> str:
    try:
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(data)


def log_line(kind: str, title: str, message: str = "") -> None:
    emoji = EMOJIS.get(kind, "•")
    if message:
        print(f"{emoji} [{_ts()}] {title}: {message}")
    else:
        print(f"{emoji} [{_ts()}] {title}")


def log_block(kind: str, title: str, data: Any) -> None:
    emoji = EMOJIS.get(kind, "•")
    print(f"\n{emoji} [{_ts()}] {title}")
    print(_pretty(data))


def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    prefix = "📨"
    lowered = (event_type or "").lower()

    if "emotion" in lowered:
        prefix = EMOJIS["emotion"]
    elif "timer" in lowered:
        prefix = EMOJIS["timer"]
    elif "sensor" in lowered:
        if payload.get("fall"):
            prefix = EMOJIS["fall"]
        elif payload.get("wandering"):
            prefix = EMOJIS["wander"]

    trace_id = payload.get("trace_id", "no-trace")
    print(f"\n{prefix} [{_ts()}] EVENT RECEIVED → {event_type} | trace={trace_id}")
    print(_pretty(payload))


def log_latency(row: Dict[str, Any]) -> None:
    trace_id = row.get("trace_id", "no-trace")
    event_type = row.get("event_type", "unknown")
    e2e = row.get("end_to_end_delay")
    brain = row.get("brain_processing_delay")
    ui = row.get("ui_write_delay")

    print(
        f"⚡ [{_ts()}] LATENCY | {event_type} | trace={trace_id} | "
        f"e2e={_fmt(e2e)}s | brain={_fmt(brain)}s | ui={_fmt(ui)}s"
    )


def _fmt(value: Any) -> str:
    try:
        return f"{float(value):.6f}"
    except Exception:
        return "n/a"