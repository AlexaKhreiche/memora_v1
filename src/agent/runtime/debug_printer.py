from __future__ import annotations

import json
import os
from agent.runtime.debug_log import debug_print
from typing import Any, Dict, Optional


LINE = "─" * 60


def _as_pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _truncate(text: Optional[str], limit: int = 120) -> str:
    if not text:
        return ""
    text = str(text).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def print_banner(title: str, emoji: str = "🔹") -> None:
    print(f"\n{emoji} {title}")
    print(LINE)


def print_kv(label: str, value: Any) -> None:
    print(f"{label:<12}: {value}")


def print_status(message: str) -> None:
    debug_print(f"✅ {message}")


def print_error(message: str) -> None:
    print(f"❌ {message}")


def print_brain_stable_emotion(label: str, confidence: float, duration_s: float) -> None:
    print(f"🧠 BRAIN | stable emotion={label} | conf={confidence:.2f} | for={duration_s:.1f}s")


def print_emotion_update(payload: Dict[str, Any]) -> None:
    print(
        "😊 EMOTION | "
        f"label={payload.get('emotion_label')} | "
        f"conf={float(payload.get('emotion_confidence', 0.0)):.2f} | "
        f"risk={payload.get('risk_level')} ({float(payload.get('risk_score', 0.0)):.2f}) | "
        f"source={payload.get('source', 'unknown')}"
    )


def print_sensor_alert(payload: Dict[str, Any]) -> None:
    print(
        "🛡️ SAFETY | "
        f"fall={payload.get('fall', False)} ({float(payload.get('fall_conf', 0.0)):.2f}) | "
        f"wandering={payload.get('wandering', False)} ({float(payload.get('wandering_conf', 0.0)):.2f})"
    )


def print_patient_message(text: str, language: Optional[str] = None, confidence: Optional[float] = None) -> None:
    suffix = []
    if language:
        suffix.append(f"lang={language}")
    if confidence is not None:
        suffix.append(f"conf={confidence:.2f}")

    meta = f" ({', '.join(suffix)})" if suffix else ""
    print(f"💬 PATIENT{meta} | {str(text).replace(chr(10), ' ')}")


def print_avatar_response(text: str, intervention: Optional[str] = None) -> None:
    print(f"🤖 AVATAR [intervention={intervention or 'none'}] | {str(text).replace(chr(10), ' ')}")


def print_timer_tick() -> None:
    print("⏰ TIMER | periodic reminder/schedule check")


def print_caregiver_alert_sent() -> None:
    print("🚨 CAREGIVER ALERT | sent=True")


def print_ui_payload_summary(payload: Dict[str, Any]) -> None:
    print_banner("UI PAYLOAD", "📦")
    print_kv("patient", f"{payload.get('patient_name', '')} ({payload.get('patient_id', '')})")
    print_kv("phase", payload.get("phase"))
    print_kv(
        "emotion",
        f"{payload.get('stable_emotion')} ({float(payload.get('stable_emotion_confidence', 0.0)):.2f})",
    )
    print_kv("intervention", payload.get("current_intervention"))
    print_kv(
        "risk",
        f"{payload.get('risk_level')} ({float(payload.get('risk_score', 0.0)):.2f})",
    )
    print_kv("fall", payload.get("fall_active"))
    print_kv("wandering", payload.get("wandering_active"))
    print_kv("alert sent", payload.get("caregiver_alert_sent"))
    print_kv("language", payload.get("response_language"))
    print_kv("mode", payload.get("interaction_mode"))
    print_kv("text", _truncate(payload.get("text_to_say", ""), 140))
    print_kv("actions", ", ".join(payload.get("avatar_actions", [])))
    print_kv(
        "logs",
        (
            f"emotions={len(payload.get('emotion_log', []))} "
            f"safety={len(payload.get('safety_log', []))} "
            f"alerts={len(payload.get('alerts', []))} "
            f"reminders={len(payload.get('reminders_due', []))}"
        ),
    )
    print_kv("updated_at", payload.get("updated_at"))
    print(LINE)


def print_full_payload_if_enabled(payload: Dict[str, Any]) -> None:
    """
    Set DEBUG_FULL_UI_PAYLOAD=1 if you want the full pretty JSON dump too.
    """
    if os.getenv("DEBUG_FULL_UI_PAYLOAD", "0") == "1":
        print("📦 FULL UI PAYLOAD JSON")
        print(_as_pretty_json(payload))
        print(LINE)

class LiveConsole:
    """Only repeat status when its meaningful state changes."""
    def __init__(self):
        self.previous = {}

    def changed(self, key, value, message):
        if self.previous.get(key) != value:
            print(message)
            self.previous[key] = value

    def update(self, state, event=None):
        if event is not None and str(event.type.value) == "EMOTION_UPDATE":
            payload = event.payload
            identity = payload.get("identity_status")
            if identity:
                self.changed("identity", identity, f"IDENTITY | {identity}")
            label = payload.get("emotion_label", "uncertain")
            source = payload.get("source", "unknown")
            percent = round(float(payload.get("emotion_confidence", 0)) * 100)
            # Ignore small score fluctuations, but always show a source/label change.
            self.changed("emotion", (label, source, percent // 10),
                         f"EMOTION | {label} ({percent}%) | source={source}")
        intervention = state.active_intervention or "none"
        self.changed("intervention", intervention, f"INTERVENTION | {intervention}")
        safety = (state.fall_active, state.wandering_active)
        self.changed("safety", safety,
                     f"SAFETY | active={'yes' if any(safety) else 'no'} | fall={safety[0]} | wandering={safety[1]}")
