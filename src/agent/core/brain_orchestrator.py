from __future__ import annotations

from agent.runtime.debug_log import debug_print

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
import json

import yaml
import time
import re

from models.state import SessionState
from models.tools_schemas.transcript_report import TranscriptReport
from models.tools_schemas.emotion_safety_detector_report import SignalReport
from models.tools_schemas.daily_reminder_report import ReminderReport
from models.answer import AnswerPayload
from models.shared import EmotionLabel, RiskLevel
from models.decision import ActionType
from agent.runtime.debug_log import log_block, log_line, log_latency

from agent.core.rules import Event, EventType, choose_decision, _emotion_to_mode
from agent.toolsimplementations.tools.daily_reminder_tool import check_caregiver_schedule
from agent.toolsimplementations.interventions.registry import get_intervention

from agent.runtime.ui_state_writer import write_ui_payload
from agent.runtime.latency_logger import log_latency_row
from agent.llm.responder import ProtocolResponder



class BrainOrchestrator:
    """
    Central brain of the MVP.

    Responsibilities:
    - receive events from monitors/tools
    - maintain current state
    - stabilize face emotion over time
    - choose the intervention/action
    - load YAML interaction protocols for patient-facing modes
    - build patient-specific context
    - delegate response generation to intervention handlers
    - send caregiver alerts when needed
    """

    def __init__(self) -> None:
        try:
            self.protocol_responder = ProtocolResponder()
        except Exception as e:
            print(f"⚠️ ProtocolResponder disabled: {e}")
            self.protocol_responder = None

        self.src_root = Path(__file__).resolve().parents[2]   # .../src
        self.project_root = self.src_root.parent
        self.data_root = self.project_root / "data" / "patients"
        self.protocol_root = (
            self.src_root
            / "agent"
            / "toolsimplementations"
            / "interventions"
            / "interaction_protocols"
        )

        self._profile_cache: Dict[str, Dict[str, Any]] = {}
        self._profile_mtime: Dict[str, float] = {}
        self._protocol_cache: Dict[str, Dict[str, Any]] = {}


    # Public entrypoint

    def handle_event(self, state: SessionState, event: Event) -> AnswerPayload:
        log_line("brain", "HANDLE EVENT", f"{event.type}")

        if event.type == EventType.SYSTEM_START:
            return self._handle_system_start(state)

        if event.type == EventType.SENSOR_ALERT:
            return self._handle_sensor_alert(state, event)

        if event.type == EventType.EMOTION_UPDATE:
            return self._handle_emotion_update(state, event)

        if event.type == EventType.PATIENT_MESSAGE:
            return self._handle_patient_message(state, event)

        if event.type == EventType.TIMER_TICK:
            return self._handle_timer_tick(state)

        log_line("warn", "UNKNOWN EVENT", f"{event.type}")
        out = AnswerPayload(text_to_say="", avatar_actions=[], ui_actions=[])
        return self._finalize_output(state, out)

    # Event handlers
    
    def _handle_system_start(self, state: SessionState) -> AnswerPayload:
        state.phase = "BOOT"

        profile = self._load_patient_profile(state.patient_id)
        patient = profile.get("patient", {}) if isinstance(profile, dict) else {}

        patient_name = (
            patient.get("preferred_name")
            or profile.get("preferred_name")
            or profile.get("name")
            or profile.get("name")
            or ""
        )

        preferred_language = self._normalize_language_code(
            patient.get("preferred_language")
            or profile.get("preferred_language")
            or patient.get("language")
            or profile.get("language")
            or "en"
        )

        if preferred_language == "ar":
            text = f"مرحباً {patient_name}. كيف تشعرين اليوم؟" if patient_name else "مرحباً. كيف تشعرين اليوم؟"
        else:
            text = f"Hello, my name is Maria. It's good to see you {patient_name}, how are you feeling today?"

        out = AnswerPayload(
            text_to_say=text,
            avatar_actions=["gentle_smile", "listening_pose"],
            ui_actions=[],
            response_language=preferred_language,
            interaction_mode="speaking",
            speech_style={
                "pace": "slow",
                "tone": "warm",
                "volume": "soft",
                "voice_hint": "gentle",
            },
        )

        state.phase = "WAITING"
        return self._finalize_output(state, out)

    def _handle_sensor_alert(self, state: SessionState, event: Event) -> AnswerPayload:
        if event.payload.get("patient_returned") is True:
            state.wandering_active = False
            state.wandering_active_since_iso = None
            if state.last_signals is not None:
                state.last_signals.wandering_detected = False
                state.last_signals.wandering_confidence = 0.0
            self._append_safety_log(state=state, event_type="wandering", active=False,
                                    confidence=0.0, reasons=["Enrolled patient re-identified"])
            return self._finalize_output(state, AnswerPayload())

        state.phase = "PROCESSING"

        signals = self._build_sensor_signals_from_event(event.payload)
        state.last_signals = signals

        decision = choose_decision(
            state=state,
            transcript=None,
            signals=signals,
            reminders=None,
        )
        state.last_decision = decision

        debug_print("=== SENSOR ALERT DEBUG ===")
        debug_print("Decision:", decision.action)
        debug_print("Signals:", state.last_signals)
        debug_print("Transcript:", None)

        action_name = self._action_name(decision.action)

        if "fall" in event.payload and not signals.fall_detected:
            state.fall_active = False
            state.fall_active_since_iso = None

        if "wandering" in event.payload and not signals.wandering_detected:
            state.wandering_active = False
            state.wandering_active_since_iso = None

        if action_name == "fall_protocol":
            log_line("fall", "FALL DETECTED", "Executing fall protocol")

            state.fall_active = True
            state.fall_active_since_iso = self._now_iso()
            state.last_fall_alert_iso = self._now_iso()

            self._append_safety_log(
                state=state,
                event_type="fall",
                active=True,
                confidence=float(signals.fall_confidence),
                reasons=event.payload.get("fall_reasons", []),
            )

            self._append_caregiver_alert(
                state=state,
                alert_type="fall",
                severity="critical",
                message="Possible fall detected. Caregiver attention may be needed.",
            )

            self._send_caregiver_alert("FALL", state.patient_id)

            protocol = self._load_protocol(decision.action)
            context = self._build_context(
                state=state,
                transcript=None,
                signals=signals,
                reminders=None,
                decision_action=decision.action,
            )

            out = self._run_intervention(
                action=decision.action,
                protocol=protocol,
                context=context,
                transcript=None,
                reminders=None,
            )
            out.caregiver_alert_sent = True

        elif action_name in {"wandering_alert", "wandering_protocol"}:
            log_line("wander", "WANDERING DETECTED", "Executing safety alert flow")

            state.wandering_active = True
            state.wandering_active_since_iso = self._now_iso()
            state.last_wandering_alert_iso = self._now_iso()

            self._append_safety_log(
                state=state,
                event_type="wandering",
                active=True,
                confidence=float(signals.wandering_confidence),
                reasons=event.payload.get("wandering_reasons", []),
            )

            self._append_caregiver_alert(
                state=state,
                alert_type="wandering",
                severity="warning",
                message="Possible wandering / out-of-frame event detected.",
            )

            self._send_caregiver_alert("WANDERING", state.patient_id)

            out = AnswerPayload(
                text_to_say="",
                avatar_actions=[],
                ui_actions=[],
                caregiver_alert_sent=True,
            )

        else:
            log_line("warn", "SENSOR ALERT", f"No special protocol selected ({action_name})")
            out = AnswerPayload(text_to_say="", avatar_actions=[], ui_actions=[])

        state.phase = "WAITING"
        return self._finalize_output(state, out)

    def _handle_emotion_update(self, state: SessionState, event: Event) -> AnswerPayload:
        payload = event.payload or {}

        if state.last_signals is None:
            state.last_signals = self._empty_signals()

        raw_label = self._coerce_emotion_label(payload.get("emotion_label", "neutral"))
        raw_conf = self._bounded_float(payload.get("emotion_confidence", 0.0))
        raw_risk_level = self._coerce_risk_level(payload.get("risk_level", "low"))
        raw_risk_score = self._bounded_float(payload.get("risk_score", 0.0))

        state.last_signals.emotion_label = raw_label
        state.last_signals.emotion_confidence = raw_conf
        state.last_signals.risk_level = raw_risk_level
        state.last_signals.risk_score = raw_risk_score

        self._append_emotion_history(
            state=state,
            label=raw_label.value,
            confidence=raw_conf,
            source=payload.get("source", "face"),
        )

        self._append_live_emotion_log(
            state=state,
            label=raw_label.value,
            confidence=raw_conf,
            risk_level=raw_risk_level.value,
            risk_score=raw_risk_score,
            source=payload.get("source", "face"),
        )

        self._update_stable_emotion_state(state)

        if raw_risk_level.value in {"medium", "high", "critical"}:
            severity = "warning" if raw_risk_level.value == "medium" else "critical"
            self._append_caregiver_alert(
                state=state,
                alert_type="emotion_risk",
                severity=severity,
                message=f"Elevated emotional risk detected: {raw_label.value}.",
            )

        debug_print(
            "[BRAIN] stable emotion:",
            state.stable_emotion_label,
            f"{state.stable_emotion_confidence:.2f}",
            f"for {self._stable_emotion_duration_seconds(state):.1f}s",
        )

        out = AnswerPayload(text_to_say="", avatar_actions=[], ui_actions=[])
        return self._finalize_output(state, out)


    def _handle_patient_message(self, state: SessionState, event: Event) -> AnswerPayload:
        state.phase = "PROCESSING"
        state.last_patient_message_iso = self._now_iso()
        
        transcript = TranscriptReport(
            transcript=(event.payload.get("text", "") or "").strip(),
            confidence=self._bounded_float(event.payload.get("confidence", 1.0)),
            language=event.payload.get("language"),
        )

        patient_text = transcript.transcript.strip()
        detected_intent = self._detect_intent(patient_text)
        detected_topic = self._extract_topic(patient_text)

        state.last_detected_intent = detected_intent

        if detected_topic:
            state.current_topic = detected_topic
            if not state.recent_topics or state.recent_topics[-1] != detected_topic:
                state.recent_topics.append(detected_topic)
                state.recent_topics = state.recent_topics[-5:]

        reminders = check_caregiver_schedule(state)

        fused_signals = self._fuse_message_signals(
            current_signals=state.last_signals,
        )

        state.last_transcript = transcript
        state.last_signals = fused_signals
        state.last_reminders = reminders

        decision = choose_decision(
            state=state,
            transcript=transcript,
            signals=fused_signals,
            reminders=reminders,
        )

        proposed_action = self._action_name(decision.action)

        if proposed_action in {"conversation", "de_escalation", "reminiscence"}:
            if not self._can_switch_intervention(state, proposed_action):
                current = state.active_intervention or "conversation"

                if current == "de_escalation":
                    decision.action = ActionType.de_escalation
                elif current == "reminiscence":
                    decision.action = ActionType.reminiscence
                else:
                    decision.action = ActionType.conversation


        state.last_decision = decision
        self._set_active_intervention(state, self._action_name(decision.action))

        debug_print("=== PATIENT MESSAGE DEBUG ===")
        debug_print("Decision:", decision.action)
        debug_print("Signals:", state.last_signals)
        debug_print("Transcript:", transcript.transcript if transcript else None)

        action_name = self._action_name(decision.action)

        if action_name == "de_escalation":
            log_line("brain", "INTERVENTION", "Selected de_escalation")
        elif action_name == "reminiscence":
            log_line("brain", "INTERVENTION", "Selected reminiscence")
        elif action_name == "conversation":
            log_line("brain", "INTERVENTION", "Selected conversation")
        elif action_name in {"caregiver_reminder_alert", "reminder_delivery"}:
            log_line("timer", "INTERVENTION", "Selected reminder delivery")
        elif action_name in {"wandering_alert", "wandering_protocol"}:
            log_line("wander", "INTERVENTION", "Selected wandering alert")
        elif action_name == "fall_protocol":
            log_line("fall", "INTERVENTION", "Selected fall protocol")
        else:
            log_line("brain", "INTERVENTION", f"Selected {action_name}")


        if action_name in {"caregiver_reminder_alert", "reminder_delivery"}:
            reminder_titles = []
            if reminders and reminders.reminders_due:
                for r in reminders.reminders_due:
                    if hasattr(r, "title"):
                        reminder_titles.append(r.title)
                    elif isinstance(r, dict):
                        reminder_titles.append(str(r.get("title", "Activity")))
                    else:
                        reminder_titles.append("Activity")

            reminder_message = (
                "Upcoming activity reminder: " + ", ".join(reminder_titles)
                if reminder_titles
                else "Upcoming activity reminder."
            )

            self._append_caregiver_alert(
                state=state,
                alert_type="reminder",
                severity="info",
                message=reminder_message,
            )

            self._send_caregiver_alert("REMINDER", state.patient_id)
            out = AnswerPayload(
                text_to_say="",
                avatar_actions=[],
                ui_actions=[],
                caregiver_alert_sent=True,
            )

        elif action_name in {"wandering_alert", "wandering_protocol"}:
            self._send_caregiver_alert("WANDERING", state.patient_id)
            out = AnswerPayload(
                text_to_say="",
                avatar_actions=[],
                ui_actions=[],
                caregiver_alert_sent=True,
            )

        else:
            protocol = self._load_protocol(decision.action)
            context = self._build_context(
                state=state,
                transcript=transcript,
                signals=fused_signals,
                reminders=reminders,
                decision_action=decision.action,
            )

            out = self._run_intervention(
                action=decision.action,
                protocol=protocol,
                context=context,
                transcript=transcript,
                reminders=reminders,
            )

            patient_text = transcript.transcript.strip()
            action_name = self._action_name(decision.action)
            protocol_name = self._protocol_name_for_action_name(action_name)

            if self.protocol_responder is not None:
                try:
                    language_prefs = self._get_patient_language_preferences(state.patient_id)

                    context = self._build_context(
                        state=state,
                        transcript=transcript,
                        signals=fused_signals,
                        reminders=None,
                        decision_action=decision.action,
                    )

                    
                    llm_result = self.protocol_responder.generate_response(
                        protocol_name=protocol_name,
                        patient_text=patient_text,
                        patient_id=state.patient_id,
                        stable_emotion=getattr(state, "stable_emotion_label", None),
                        current_intervention=getattr(state, "active_intervention", None),
                        risk_level=str(getattr(fused_signals, "risk_level", "low")),
                        risk_score=float(getattr(fused_signals, "risk_score", 0.0)),
                        preferred_language=language_prefs["preferred_language"],
                        dialect_hint=language_prefs.get("dialect_hint"),
                        input_language=self._normalize_language_code(getattr(transcript, "language", None)),
                        conversation_history=list(state.conversation_history),
                        patient_name=context.get("patient_name"),
                        comfort_topics=context.get("comfort_topics"),
                        music_favorites=context.get("music_favorites"),
                        do_not_discuss=context.get("do_not_discuss"),
                        family_key_people=context.get("family_key_people"),
                        detected_intent=context.get("detected_intent"),
                        current_topic=context.get("current_topic"),
                        recent_topics=context.get("recent_topics"),
                        turns_since_avatar_question=context.get("turns_since_avatar_question"),
                    )

                    if llm_result.get("text_to_say"):
                        out.text_to_say = llm_result["text_to_say"]

                    if llm_result.get("avatar_actions"):
                        out.avatar_actions = llm_result["avatar_actions"]

                    if llm_result.get("response_language"):
                        out.response_language = llm_result["response_language"]

                    if llm_result.get("interaction_mode"):
                        out.interaction_mode = llm_result["interaction_mode"]

                    if llm_result.get("speech_style"):
                        out.speech_style = llm_result["speech_style"]

                except Exception as e:
                    print(f"[LLM ERROR] {e}")
            
            # Append this turn to conversation history for LLM context
            if patient_text:
                state.conversation_history.append({"role": "patient", "content": patient_text})
            if out.text_to_say:
                state.conversation_history.append({"role": "assistant", "content": out.text_to_say})

            if out.text_to_say and "?" in out.text_to_say:
                state.turns_since_avatar_question = 0
            else:
                state.turns_since_avatar_question += 1

            # Keep only the last 8 entries (4 turns)
            state.conversation_history = state.conversation_history[-8:]

            debug_print("Rendered response:", out.text_to_say)

        state.turn_index += 1
        state.phase = "WAITING"
        return self._finalize_output(state, out)


    def _handle_timer_tick(self, state: SessionState) -> AnswerPayload:
        log_line("timer", "TIMER TICK", "Checking caregiver schedule")

        state.phase = "PROCESSING"

        # Inactivity check — trigger a check-in if patient hasn't spoken in 40s
        INACTIVITY_THRESHOLD_S = 40.0
        last_msg_ts = self._parse_iso(state.last_patient_message_iso)
        seconds_since_message = (datetime.now(timezone.utc) - last_msg_ts).total_seconds() if last_msg_ts else 0.0
        if last_msg_ts is not None and seconds_since_message >= INACTIVITY_THRESHOLD_S:
            log_line("timer", "INACTIVITY", f"No patient message for {seconds_since_message:.0f}s — triggering check-in")
            state.last_patient_message_iso = self._now_iso()  # reset so it doesn't fire every tick

            language_prefs = self._get_patient_language_preferences(state.patient_id)
            patient_name = self._build_context(
                state=state,
                transcript=None,
                signals=state.last_signals,
                reminders=None,
                decision_action=ActionType.conversation,
            ).get("patient_name") or ""
            
            if language_prefs["preferred_language"] == "ar":
                check_in_text = (
                    f"مرحباً {patient_name}، أنا ما زلت هنا معك. هل تحبين أن نتحدث قليلاً؟"
                    if patient_name
                    else "أنا ما زلت هنا معك. هل تحبين أن نتحدث قليلاً؟"
                )
            else:
                check_in_text = (
                    f"Hi {patient_name}, I'm still here with you. Would you like to chat for a moment?"
                    if patient_name
                    else "I'm still here with you. Would you like to chat for a moment?"
                )

            out = AnswerPayload(
                text_to_say=check_in_text,
                avatar_actions=self._avatar_actions_for_action(ActionType.conversation),
                ui_actions=[],
            )
            state.phase = "WAITING"
            return self._finalize_output(state, out)

        reminders = check_caregiver_schedule(state)
        state.last_reminders = reminders

        decision = choose_decision(
            state=state,
            transcript=None,
            signals=state.last_signals,
            reminders=reminders,
        )
        state.last_decision = decision

        action_name = self._action_name(decision.action)

        if action_name in {"caregiver_reminder_alert", "reminder_delivery"}:
            log_line("timer", "INTERVENTION", "Selected reminder delivery")

            reminder_titles = []
            if reminders and reminders.reminders_due:
                for r in reminders.reminders_due:
                    if hasattr(r, "title"):
                        reminder_titles.append(r.title)
                    elif isinstance(r, dict):
                        reminder_titles.append(str(r.get("title", "Activity")))
                    else:
                        reminder_titles.append("Activity")

            reminder_message = (
                "Upcoming activity reminder: " + ", ".join(reminder_titles)
                if reminder_titles
                else "Upcoming activity reminder."
            )

            self._append_caregiver_alert(
                state=state,
                alert_type="reminder",
                severity="info",
                message=reminder_message,
            )

            self._send_caregiver_alert("REMINDER", state.patient_id)
            out = AnswerPayload(
                text_to_say="",
                avatar_actions=[],
                ui_actions=[],
                caregiver_alert_sent=True,
            )
        else:
            log_line("timer", "INTERVENTION", f"No reminder action ({action_name})")
            out = AnswerPayload(text_to_say="", avatar_actions=[], ui_actions=[])

        state.phase = "WAITING"
        return self._finalize_output(state, out)

    # Helpers: UI payload

    def _build_ui_payload(
        self,
        state: SessionState,
        out: AnswerPayload,
    ) -> Dict[str, Any]:
        signals = state.last_signals
        displayed_text = out.text_to_say if out.text_to_say else state.last_output_text
        avatar_actions = (
            out.avatar_actions
            if out.avatar_actions
            else state.last_ui_payload.get("avatar_actions", [])
        )

        response_language = (
            out.response_language
            or state.last_ui_payload.get("response_language")
            or self._get_patient_language_preferences(state.patient_id)["preferred_language"]
        )

        interaction_mode = (
            out.interaction_mode
            or state.last_ui_payload.get("interaction_mode")
            or "idle"
        )

        speech_style = (
            out.speech_style
            if out.speech_style
            else state.last_ui_payload.get("speech_style", {})
        )

        profile = self._load_patient_profile(state.patient_id)
        patient = profile.get("patient", {}) if isinstance(profile, dict) else {}

        patient_name = (
            patient.get("name")
            or profile.get("name")
            or profile.get("preferred_name")
            or ""
        )
        
        trace = getattr(state, "current_trace", {}) or {}


        return {
            "patient_id": state.patient_id,
            "patient_name": patient_name,
            "phase": state.phase,
            "stable_emotion": state.stable_emotion_label,
            "stable_emotion_confidence": state.stable_emotion_confidence,
            "current_intervention": state.active_intervention or self._compute_intervention_group(state),
            "text_to_say": displayed_text,
            "avatar_actions": avatar_actions,
            "response_language": response_language,
            "interaction_mode": interaction_mode,
            "speech_style": speech_style,
            "fall_active": state.fall_active,
            "wandering_active": state.wandering_active,
            "caregiver_alert_sent": out.caregiver_alert_sent,
            "risk_level": signals.risk_level.value if signals else "low",
            "risk_score": float(signals.risk_score) if signals else 0.0,
            "updated_at": self._now_iso(),
            "last_transcript": (
                state.last_transcript.transcript
                if state.last_transcript
                else ""
            ),
            "emotion_log": getattr(state, "live_emotion_log", [])[-30:],
            "safety_log": getattr(state, "safety_log", [])[-30:],
            "alerts": getattr(state, "caregiver_alerts", [])[-30:],
            "reminders_due": [
                r.model_dump() if hasattr(r, "model_dump") else dict(r)
                for r in (state.last_reminders.reminders_due if state.last_reminders else [])
            ],
            "next_reminder_iso": (
                state.last_reminders.next_reminder_iso
                if state.last_reminders
                else None
            ),
            "trace_id": trace.get("trace_id"),
            "event_type": trace.get("event_type"),
            "t_created": trace.get("t_created"),
            "t_published": trace.get("t_published"),
            "t_received": trace.get("t_received"),
        }
        

    def _finalize_output(self, state: SessionState, out: AnswerPayload) -> AnswerPayload:
        if out.text_to_say:
            state.last_output_text = out.text_to_say

        trace = getattr(state, "current_trace", {}) or {}

        t_finalized = time.perf_counter()

        state.last_ui_payload = self._build_ui_payload(state, out)
        state.last_ui_payload["t_finalized"] = t_finalized

        write_start = time.perf_counter()
        write_ui_payload(state.last_ui_payload)
        write_end = time.perf_counter()

        state.last_ui_payload["t_ui_written"] = write_end

        t_created = trace.get("t_created")
        t_published = trace.get("t_published")
        t_received = trace.get("t_received")

        def safe_diff(a, b):
            if a is None or b is None:
                return None
            return a - b

        latency_row = {
            "trace_id": trace.get("trace_id"),
            "event_type": trace.get("event_type"),
            "t_created": t_created,
            "t_published": t_published,
            "t_received": t_received,
            "t_finalized": t_finalized,
            "t_ui_written": write_end,
            "source_to_bus_delay": safe_diff(t_published, t_created),
            "bus_wait_delay": safe_diff(t_received, t_published),
            "brain_processing_delay": safe_diff(t_finalized, t_received),
            "ui_write_delay": safe_diff(write_end, write_start),
            "end_to_end_delay": safe_diff(write_end, t_created),
        }

        if latency_row["trace_id"] and latency_row["event_type"]:
            log_latency_row(latency_row)

        log_block("ui", "UI PAYLOAD", state.last_ui_payload)
        log_latency(latency_row)
        return out

    # Helpers: intervention dispatch

    def _run_intervention(
        self,
        action: ActionType,
        protocol: Dict[str, Any],
        context: Dict[str, Any],
        transcript: Optional[TranscriptReport] = None,
        reminders: Optional[ReminderReport] = None,
    ) -> AnswerPayload:
        handler = get_intervention(action)

        if handler is None:
            fallback_text = self._render_response_text(
                action=action,
                protocol=protocol,
                context=context,
                transcript=transcript,
                reminders=reminders,
            )
            return AnswerPayload(
                text_to_say=fallback_text,
                avatar_actions=self._avatar_actions_for_action(action),
                ui_actions=[],
                caregiver_alert_sent=False,
            )

        out = handler.build_response(
            action=action,
            protocol=protocol,
            context=context,
            transcript=transcript,
            reminders=reminders,
        )

        if not out.avatar_actions:
            out.avatar_actions = self._avatar_actions_for_action(action)

        return out

    # Helpers: emotion stabilization
    def _parse_iso(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    def _append_emotion_history(
        self,
        state: SessionState,
        label: str,
        confidence: float,
        source: str = "face",
    ) -> None:
        now = datetime.now(timezone.utc)

        state.emotion_history.append(
            {
                "label": label,
                "confidence": float(confidence),
                "source": source,
                "ts": now.isoformat(),
            }
        )

        cutoff = now - timedelta(seconds=4)
        kept = []
        for item in state.emotion_history:
            ts = self._parse_iso(item.get("ts"))
            if ts is not None and ts >= cutoff:
                kept.append(item)

        state.emotion_history = kept
        
    def _append_live_emotion_log(
        self,
        state: SessionState,
        label: str,
        confidence: float,
        risk_level: str,
        risk_score: float,
        source: str = "face",
    ) -> None:
        state.live_emotion_log.append(
            {
                "id": f"emotion_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "label": label,
                "confidence": float(confidence),
                "risk_level": risk_level,
                "risk_score": float(risk_score),
                "source": source,
                "timestamp": self._now_iso(),
            }
        )
        state.live_emotion_log = state.live_emotion_log[-50:]


    def _append_safety_log(
        self,
        state: SessionState,
        event_type: str,
        active: bool,
        confidence: float,
        reasons: Optional[list[str]] = None,
    ) -> None:
        state.safety_log.append(
            {
                "id": f"safety_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "type": event_type,
                "active": bool(active),
                "confidence": float(confidence),
                "reasons": reasons or [],
                "timestamp": self._now_iso(),
            }
        )
        state.safety_log = state.safety_log[-50:]


    def _append_caregiver_alert(
        self,
        state: SessionState,
        alert_type: str,
        severity: str,
        message: str,
    ) -> None:
        state.caregiver_alerts.append(
            {
                "id": f"alert_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": self._now_iso(),
                "acknowledged": False,
            }
        )
        state.caregiver_alerts = state.caregiver_alerts[-50:]

    def _compute_stable_emotion(self, state: SessionState) -> tuple[str, float]:
        if not state.emotion_history:
            return "neutral", 0.0

        label_scores: Dict[str, float] = {}
        for item in state.emotion_history:
            label = str(item.get("label", "neutral")).lower()
            conf = float(item.get("confidence", 0.0))
            label_scores[label] = label_scores.get(label, 0.0) + conf

        if not label_scores:
            return "neutral", 0.0

        best_label = max(label_scores, key=label_scores.get)
        best_score = label_scores[best_label]

        # Report unavailable current observations immediately, not stale certainty.
        latest = state.emotion_history[-1]
        if float(latest.get("confidence", 0.0)) <= 0:
            return "uncertain", 0.0
        matching = [item for item in state.emotion_history if str(item.get("label", "neutral")).lower() == best_label]
        stable_conf = best_score / len(matching) if matching else 0.0
        return best_label, stable_conf

    def _compute_intervention_group(self, state: SessionState) -> str:
        if not state.emotion_history:
            return "conversation"

        grouped_scores: Dict[str, float] = {
            "de_escalation": 0.0,
            "reminiscence": 0.0,
            "conversation": 0.0,
        }

        for item in state.emotion_history:
            label = str(item.get("label", "neutral")).lower()
            conf = float(item.get("confidence", 0.0))

            grouped_scores[_emotion_to_mode(label)] += conf

        if not any(grouped_scores.values()):
            return "conversation"

        return max(grouped_scores, key=grouped_scores.get)

    def _update_stable_emotion_state(self, state: SessionState) -> None:
        stable_label, stable_conf = self._compute_stable_emotion(state)

        now_iso = self._now_iso()

        if state.stable_emotion_label != stable_label:
            state.stable_emotion_label = stable_label
            state.stable_emotion_confidence = stable_conf
            state.stable_emotion_since_iso = now_iso
        else:
            state.stable_emotion_confidence = stable_conf
            if state.stable_emotion_since_iso is None:
                state.stable_emotion_since_iso = now_iso

    def _stable_emotion_duration_seconds(self, state: SessionState) -> float:
        ts = self._parse_iso(state.stable_emotion_since_iso)
        if ts is None:
            return 0.0
        return (datetime.now(timezone.utc) - ts).total_seconds()

    def _set_active_intervention(self, state: SessionState, action_name: str) -> None:
        if state.active_intervention != action_name:
            state.active_intervention = action_name
            state.active_intervention_since_iso = self._now_iso()

    def _active_intervention_duration_seconds(self, state: SessionState) -> float:
        ts = self._parse_iso(state.active_intervention_since_iso)
        if ts is None:
            return 0.0
        return (datetime.now(timezone.utc) - ts).total_seconds()

    def _can_switch_intervention(self, state: SessionState, new_action: str) -> bool:
        if state.active_intervention is None:
            return True

        if state.active_intervention == new_action:
            return True

        hold_seconds = {
            "de_escalation": 15.0,
            "reminiscence": 20.0,
            "conversation": 5.0,
        }

        current_hold = hold_seconds.get(state.active_intervention, 5.0)
        return self._active_intervention_duration_seconds(state) >= current_hold

    # Helpers: signal building / fusion
    def _empty_signals(self) -> SignalReport:
        return SignalReport(
            emotion_label=EmotionLabel.neutral,
            emotion_confidence=0.0,
            fall_detected=False,
            fall_confidence=0.0,
            wandering_detected=False,
            wandering_confidence=0.0,
            risk_score=0.0,
            risk_level=RiskLevel.low,
        )

    def _build_sensor_signals_from_event(self, payload: Dict[str, Any]) -> SignalReport:
        fall = bool(payload.get("fall", False))
        wandering = bool(payload.get("wandering", False))

        return SignalReport(
            emotion_label=EmotionLabel.uncertain,
            emotion_confidence=0.0,
            fall_detected=fall,
            fall_confidence=self._bounded_float(
                payload.get("fall_conf", 1.0 if fall else 0.0)
            ),
            wandering_detected=wandering,
            wandering_confidence=self._bounded_float(
                payload.get("wandering_conf", 1.0 if wandering else 0.0)
            ),
            risk_score=1.0 if fall else 0.9 if wandering else 0.0,
            risk_level=RiskLevel.critical if fall else RiskLevel.high if wandering else RiskLevel.low,
        )

    def _copy_signals(self, signals: SignalReport) -> SignalReport:
        if hasattr(signals, "model_copy"):
            return signals.model_copy(deep=True)
        return signals.copy(deep=True)

    def _fuse_message_signals(
        self,
        current_signals: Optional[SignalReport],
    ) -> SignalReport:
        return self._copy_signals(current_signals) if current_signals else self._empty_signals()

    # Helpers: patient profile / protocol loading
    def _load_patient_profile(self, patient_id: str) -> Dict[str, Any]:
        profile_path = self.data_root / patient_id / "profile.json"
        if not profile_path.exists():
            self._profile_cache[patient_id] = {}
            return {}

        current_mtime = profile_path.stat().st_mtime
        if patient_id in self._profile_cache and self._profile_mtime.get(patient_id) == current_mtime:
            return self._profile_cache[patient_id]

        with profile_path.open("r", encoding="utf-8") as f:
            profile = json.load(f)

        self._profile_cache[patient_id] = profile
        self._profile_mtime[patient_id] = current_mtime
        return profile

    def _get_patient_language_preferences(self, patient_id: str) -> dict[str, Any]:
            profile = self._load_patient_profile(patient_id)
            patient = profile.get("patient", {}) if isinstance(profile, dict) else {}

            preferred_language = (
                patient.get("preferred_language")
                or profile.get("preferred_language")
                or patient.get("language")
                or profile.get("language")
                or "en"
            )

            secondary_language = (
                patient.get("secondary_language")
                or profile.get("secondary_language")
            )

            dialect_hint = (
                patient.get("dialect_hint")
                or profile.get("dialect_hint")
            )

            return {
                "preferred_language": str(preferred_language).strip().lower(),
                "secondary_language": secondary_language,
                "dialect_hint": dialect_hint,
            }
            
    def _load_protocol(self, action: ActionType) -> Dict[str, Any]:
        action_name = self._action_name(action)

        if action_name in self._protocol_cache:
            return self._protocol_cache[action_name]

        filename_map = {
            "conversation": "conversation.yaml",
            "de_escalation": "de_escalation.yaml",
            "validation": "de_escalation.yaml",
            "reassurance": "de_escalation.yaml",
            "fall_protocol": "fall_protocol.yaml",
            "reminiscence": "reminiscence.yaml",
        }

        filename = filename_map.get(action_name)
        if not filename:
            return {}

        path = self.protocol_root / filename

        debug_print("=== PROTOCOL LOAD DEBUG ===")
        debug_print("Loading protocol for:", action_name)
        debug_print("Protocol path:", path)

        if not path.exists():
            print("Protocol file not found, using default.")
            protocol = self._default_protocol(action_name)
            self._protocol_cache[action_name] = protocol
            return protocol

        with path.open("r", encoding="utf-8") as f:
            protocol = yaml.safe_load(f) or {}

        debug_print("Loaded protocol keys:", list(protocol.keys()))

        self._protocol_cache[action_name] = protocol
        return protocol

    def _default_protocol(self, action_name: str) -> Dict[str, Any]:
        defaults = {
            "conversation": {
                "opening_templates": ["It’s nice to talk with you."],
            },
            "de_escalation": {
                "opening_templates": ["You’re safe. I’m here with you."],
                "grounding_templates": ["We can take this slowly."],
            },
            "fall_protocol": {
                "opening_templates": ["I’m here with you. Please stay still. Help is being notified."],
            },
            "reminiscence": {
                "opening_templates": ["Would you like something familiar right now?"],
            },
        }
        return defaults.get(action_name, {"opening_templates": ["I’m here with you."]})

    def _build_context(
        self,
        state: SessionState,
        transcript: Optional[TranscriptReport],
        signals: Optional[SignalReport],
        reminders: Optional[ReminderReport],
        decision_action: ActionType,
    ) -> Dict[str, Any]:
        profile = self._load_patient_profile(state.patient_id)

        patient = profile.get("patient", {})
        if not patient:
            patient = {
                "name": profile.get("name"),
                "preferred_name": profile.get("preferred_name"),
                "language": profile.get("language") or profile.get("preferred_language"),
                "preferred_language": profile.get("preferred_language"),
                "secondary_language": profile.get("secondary_language"),
                "dialect_hint": profile.get("dialect_hint"),
            }

        preferences = profile.get("preferences", {})
        if isinstance(preferences, str):
            preferences = {"notes": preferences}

        family_context = profile.get("family_context", {})
        care_team = profile.get("care_team", {})

        key_people = family_context.get("key_people", [])
        primary_caregiver = care_team.get("primary_caregiver", {})

        comfort_topics = preferences.get("comfort_topics", [])
        music_favorites = preferences.get("music_favorites", [])
        do_not_discuss = preferences.get("do_not_discuss", [])

        if not comfort_topics and profile.get("calming_topics"):
            comfort_topics = [profile.get("calming_topics")]

        if not do_not_discuss and profile.get("triggers_to_avoid"):
            do_not_discuss = [profile.get("triggers_to_avoid")]

        
        return {
            "patient_id": state.patient_id,
            "patient_name": patient.get("name") or patient.get("preferred_name"),
            "language": patient.get("language", "en"),
            "preferred_language": patient.get("preferred_language", patient.get("language", "en")),
            "secondary_language": patient.get("secondary_language"),
            "dialect_hint": patient.get("dialect_hint"),
            "timezone": patient.get("timezone", "Europe/Madrid"),
            "turn_index": state.turn_index,
            "current_action": self._action_name(decision_action),
            "transcript": transcript.transcript if transcript else "",
            "transcript_language": getattr(transcript, "language", None) if transcript else None,
            "emotion_label": signals.emotion_label.value if signals else "neutral",
            "emotion_confidence": float(signals.emotion_confidence) if signals else 0.0,
            "risk_level": signals.risk_level.value if signals else "low",
            "risk_score": float(signals.risk_score) if signals else 0.0,
            "stable_emotion_label": state.stable_emotion_label,
            "stable_emotion_confidence": state.stable_emotion_confidence,
            "comfort_topics": comfort_topics,
            "music_favorites": music_favorites,
            "do_not_discuss": do_not_discuss,
            "family_key_people": key_people,
            "family_history_notes": family_context.get("history_notes", ""),
            "caregiver_name": primary_caregiver.get("name"),
            "reminders_due": [r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in reminders.reminders_due] if reminders else [],
            "next_reminder_iso": reminders.next_reminder_iso if reminders else None,
            "detected_intent": state.last_detected_intent,
            "current_topic": state.current_topic,
            "recent_topics": list(state.recent_topics),
            "turns_since_avatar_question": state.turns_since_avatar_question,
        }

    # Legacy fallback renderer
    def _detect_intent(self, text: str) -> str:
        t = (text or "").strip().lower()
        if not t:
            return "silence"

        if any(p in t for p in ["who are you", "what is your name", "what's your name"]):
            return "identity_question"

        if "?" in t:
            if any(p in t for p in ["do you know", "are", "is", "can", "did", "where", "when", "who", "what"]):
                return "direct_question"
            return "question"

        if len(t.split()) <= 3:
            return "engagement_bid"

        if any(p in t for p in ["i want", "i would like", "i feel", "i'm feeling", "i am feeling"]):
            return "personal_statement"

        return "statement"

    def _extract_topic(self, text: str) -> Optional[str]:
        t = (text or "").strip().lower()
        if not t:
            return None

        topic_keywords = {
            "daughter": ["daughter", "faten"],
            "neighbors": ["neighbor", "neighbour", "neighbors", "neighbours"],
            "coffee": ["coffee", "tea"],
            "music": ["music", "song", "singing", "fairuz"],
            "family": ["family", "grandchildren", "grandchild", "son", "daughter"],
            "walking": ["walk", "walking"],
            "plants": ["plant", "plants", "garden", "gardening"],
        }

        for topic, keywords in topic_keywords.items():
            if any(word in t for word in keywords):
                return topic

        return None
    
    def _render_response_text(
        self,
        action: ActionType,
        protocol: Dict[str, Any],
        context: Dict[str, Any],
        transcript: Optional[TranscriptReport],
        reminders: Optional[ReminderReport],
    ) -> str:
        action_name = self._action_name(action)

        openings = protocol.get("opening_templates", [])
        opening = openings[0] if openings else "I’m here with you."

        grounding_templates = protocol.get("grounding_templates", [])
        grounding = grounding_templates[0] if grounding_templates else "We can take this slowly."

        patient_name = context.get("patient_name") or ""
        comfort_topics = context.get("comfort_topics") or []
        music_favorites = context.get("music_favorites") or []
        family_key_people = context.get("family_key_people") or []
        user_text = (transcript.transcript if transcript else "").strip()
        preferred_language = self._normalize_language_code(context.get("preferred_language", "en"))

        if action_name == "fall_protocol":
            if preferred_language == "ar":
                return "أنا هنا معك. من فضلك ابقي في مكانك. يتم إبلاغ المساعدة الآن."
            return opening

        if action_name in {"de_escalation", "validation", "reassurance"}:
            if preferred_language == "ar":
                return "أنتِ بأمان. أنا هنا معك. سنأخذ الأمور بهدوء."
            parts = [opening]
            if grounding and grounding not in parts:
                parts.append(grounding)

            if music_favorites:
                parts.append(f"Would it help to think about {music_favorites[0]} for a moment?")
            elif comfort_topics:
                parts.append(f"Would it help to stay with something familiar, like {comfort_topics[0]}?")

            return " ".join(parts).strip()

        if action_name == "reminiscence":
            if preferred_language == "ar":
                if music_favorites:
                    return f"هل تحبين أن نتذكر شيئاً جميلاً، مثل {music_favorites[0]}؟"
                if comfort_topics:
                    return f"يمكننا أن نتحدث عن {comfort_topics[0]} إذا أحببتِ."
                return "هل تحبين أن نتذكر شيئاً مألوفاً وجميلاً؟"

            if music_favorites:
                return f"{opening} Would you like to hear something familiar, like {music_favorites[0]}?"
            if comfort_topics:
                return f"{opening} We could talk about {comfort_topics[0]} if you’d like."
            if family_key_people:
                name = family_key_people[0].get("name")
                if name:
                    return f"{opening} We could think about {name} for a moment if that feels nice."
            return opening

        if action_name == "conversation":
            if preferred_language == "ar":
                if not user_text:
                    if patient_name:
                        return f"مرحباً {patient_name}. كيف تشعرين اليوم؟"
                    return "مرحباً. كيف تشعرين اليوم؟"
                return "أنا هنا معك."

            if not user_text:
                if patient_name:
                    return f"{opening} How are you feeling, {patient_name}?"
                return f"{opening} How are you feeling?"
            return opening

        if preferred_language == "ar":
            return "أنا هنا معك."
        return "I’m here with you."

    def _avatar_actions_for_action(self, action: ActionType) -> list[str]:
        action_name = self._action_name(action)

        mapping = {
            "conversation": ["listening_pose"],
            "de_escalation": ["soft_expression", "slow_nod"],
            "validation": ["soft_expression", "slow_nod"],
            "reassurance": ["soft_expression", "slow_nod"],
            "reminiscence": ["gentle_smile"],
            "fall_protocol": ["concerned_face"],
        }
        return mapping.get(action_name, [])

    # Helpers: normalization / utilities
    def _action_name(self, action: Any) -> str:
        if hasattr(action, "value"):
            value = str(action.value)
        else:
            value = str(action)
        return value.strip().lower()

    def _normalize_language_code(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return "unknown"

        if text.startswith("ar"):
            return "ar"
        if text.startswith("en"):
            return "en"

        return text

    def _coerce_emotion_label(self, value: Any) -> EmotionLabel:
        try:
            if isinstance(value, EmotionLabel):
                return value
            return EmotionLabel(str(value).lower())
        except Exception:
            return EmotionLabel.neutral

    def _coerce_risk_level(self, value: Any) -> RiskLevel:
        try:
            if isinstance(value, RiskLevel):
                return value
            return RiskLevel(str(value).lower())
        except Exception:
            return RiskLevel.low

    def _bounded_float(self, value: Any, low: float = 0.0, high: float = 1.0) -> float:
        try:
            x = float(value)
        except Exception:
            x = low
        return max(low, min(high, x))

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _protocol_name_for_action_name(self, action_name: str) -> str:
        mapping = {
            "conversation": "conversation",
            "reminiscence": "reminiscence",
            "de_escalation": "de_escalation",
            "validation": "de_escalation",
            "reassurance": "de_escalation",
            "fall_protocol": "fall_protocol",
            "fall": "fall_protocol",
        }
        return mapping.get(action_name, "conversation")

    def _send_caregiver_alert(self, alert_type: str, patient_id: str) -> None:
        ts = self._now_iso()
        debug_print(f"[ALERT] {ts} type={alert_type} patient={patient_id}")
