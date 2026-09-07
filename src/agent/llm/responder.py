from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from agent.llm.prompt_builder import build_protocol_prompt
from agent.llm.protocol_loader import load_protocol


def _safe_json_parse(raw_text: str) -> dict[str, Any]:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return {}

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw_text[start : end + 1])
        except json.JSONDecodeError:
            return {}

    return {}


class ProtocolResponder:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment")

        self.client = OpenAI(api_key=api_key)


    def generate_response(
        self,
        protocol_name: str,
        patient_text: str,
        patient_id: str,
        stable_emotion: str | None,
        current_intervention: str | None,
        risk_level: str | None,
        risk_score: float | None,
        preferred_language: str = "en",
        dialect_hint: str | None = None,
        input_language: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        patient_name: str | None = None,
        comfort_topics: list[str] | None = None,
        music_favorites: list[str] | None = None,
        do_not_discuss: list[str] | None = None,
        family_key_people: list[dict[str, Any]] | None = None,
        detected_intent: str | None = None,
        current_topic: str | None = None,
        recent_topics: list[str] | None = None,
        turns_since_avatar_question: int | None = None,
    ) -> dict[str, Any]:
    
        protocol = load_protocol(protocol_name)

        prompt = build_protocol_prompt(
            protocol_name=protocol_name,
            protocol=protocol,
            patient_text=patient_text,
            patient_id=patient_id,
            stable_emotion=stable_emotion,
            current_intervention=current_intervention,
            risk_level=risk_level,
            risk_score=risk_score,
            preferred_language=preferred_language,
            dialect_hint=dialect_hint,
            input_language=input_language,
            conversation_history=conversation_history,
            patient_name=patient_name,
            comfort_topics=comfort_topics,
            music_favorites=music_favorites,
            do_not_discuss=do_not_discuss,
            family_key_people=family_key_people,
            detected_intent=detected_intent,
            current_topic=current_topic,
            recent_topics=recent_topics,
            turns_since_avatar_question=turns_since_avatar_question,
        )

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an emotionally adaptive ADRD support companion. "
                        "Always return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.65,
        )

        raw_text = (
            completion.choices[0].message.content.strip()
            if completion.choices
            and completion.choices[0].message
            and completion.choices[0].message.content
            else ""
        )

        parsed = _safe_json_parse(raw_text)
        suggested_actions = protocol.get("suggested_avatar_actions", [])
        fallback_actions = suggested_actions if isinstance(suggested_actions, list) else []

        text_to_say = str(parsed.get("text_to_say", "")).strip()
        avatar_actions = parsed.get("avatar_actions", fallback_actions)
        if not isinstance(avatar_actions, list):
            avatar_actions = fallback_actions

        response_language = str(parsed.get("response_language") or preferred_language or input_language or "en").strip()
        interaction_mode = str(parsed.get("interaction_mode") or "speaking").strip()

        speech_style = parsed.get("speech_style", {})
        if not isinstance(speech_style, dict):
            speech_style = {}

        if not text_to_say:
            text_to_say = (
                "أنا هنا معك."
                if response_language.startswith("ar")
                else "I am here with you."
            )

        return {
            "text_to_say": text_to_say,
            "avatar_actions": avatar_actions,
            "response_language": response_language,
            "interaction_mode": interaction_mode,
            "speech_style": speech_style,
        }