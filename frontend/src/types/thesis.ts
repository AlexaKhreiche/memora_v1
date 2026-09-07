export type SpeechStyle = {
  pace?: string;
  tone?: string;
  volume?: string;
  voice_hint?: string;
};

export type EmotionLogItem = {
  id: string;
  label: string;
  confidence: number;
  risk_level: string;
  risk_score: number;
  source?: string;
  timestamp: string;
};

export type SafetyLogItem = {
  id: string;
  type: "fall" | "wandering" | "presence";
  active: boolean;
  confidence: number;
  reasons?: string[];
  timestamp: string;
};

export type AlertItem = {
  id: string;
  type: string;
  severity: "info" | "warning" | "critical";
  message: string;
  timestamp: string;
  acknowledged: boolean;
};

export type CaregiverContact = {
  name: string;
  relation?: string;
  phone?: string;
};

export type PatientProfile = {
  patient_id: string;
  name: string;
  preferred_name?: string;
  preferred_language?: string;
  routines?: string;
  preferences?: string;
  calming_topics?: string;
  triggers_to_avoid?: string;
  mobility_notes?: string;
  wandering_notes?: string;
  medical_notes?: string;
  communication_notes?: string;
  caregiver_contacts?: CaregiverContact[];
};

export type ReminderItem = {
  id: string;
  title: string;
  due_iso: string;
  priority?: number;
  instructions?: string | null;
};

export type UpcomingActivity = {
  id: string;
  title: string;
  time: string;
  notify_before_min?: number;
  minutes_until?: number;
  status?: "upcoming" | "later" | "passed" | "due";
  today_key?: string;
};

export type ThesisUiState = {
  patient_id: string;
  patient_name?: string;
  phase: string;
  stable_emotion: string | null;
  stable_emotion_confidence: number;
  current_intervention: string | null;
  text_to_say: string;
  avatar_actions: string[];
  response_language: string;
  interaction_mode: string;
  speech_style?: SpeechStyle;
  fall_active: boolean;
  wandering_active: boolean;
  caregiver_alert_sent: boolean;
  risk_level: string;
  risk_score: number;
  updated_at: string;
  last_transcript?: string;
  emotion_log?: EmotionLogItem[];
  safety_log?: SafetyLogItem[];
  alerts?: AlertItem[];
  reminders_due?: ReminderItem[];
  next_reminder_iso?: string | null;
  upcoming_activities?: UpcomingActivity[];
};

export const defaultThesisUiState: ThesisUiState = {
  patient_id: "P001",
  patient_name: "",
  phase: "WAITING",
  stable_emotion: null,
  stable_emotion_confidence: 0,
  current_intervention: null,
  text_to_say: "System is starting...",
  avatar_actions: [],
  response_language: "en",
  interaction_mode: "idle",
  speech_style: {
    pace: "normal",
    tone: "warm",
    volume: "soft",
    voice_hint: "gentle",
  },
  fall_active: false,
  wandering_active: false,
  caregiver_alert_sent: false,
  risk_level: "low",
  risk_score: 0,
  updated_at: new Date().toISOString(),
  last_transcript: "",
  emotion_log: [],
  safety_log: [],
  alerts: [],
  reminders_due: [],
  next_reminder_iso: null,
  upcoming_activities: [],
};

export const defaultPatientProfile: PatientProfile = {
  patient_id: "P001",
  name: "",
  preferred_name: "",
  preferred_language: "",
  routines: "",
  preferences: "",
  calming_topics: "",
  triggers_to_avoid: "",
  mobility_notes: "",
  wandering_notes: "",
  medical_notes: "",
  communication_notes: "",
  caregiver_contacts: [],
};