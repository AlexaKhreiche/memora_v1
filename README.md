# ADRD Care Assistant — Capstone Project

A real-time, multimodal AI system that monitors and supports elderly patients with **Alzheimer's Disease and Related Dementias (ADRD)**. The system combines computer vision, emotion detection, speech recognition, and a large language model to provide safety monitoring and empathetic interaction — while keeping caregivers informed.

---

## Table of Contents

- [What It Does](#what-it-does)
- [System Architecture](#system-architecture)
- [Project Structure](#project-structure)
- [Key Files Explained](#key-files-explained)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Running Tests](#running-tests)
- [API Keys & Environment Variables](#api-keys--environment-variables)

---

## What It Does

The system runs continuously and:

1. **Watches for safety events** — Uses the webcam and MediaPipe pose estimation to detect falls and wandering in real time.
2. **Reads facial emotions** — Analyzes the patient's face via the Hume AI API to detect distress, agitation, or calmness.
3. **Listens and responds** — Records the patient's speech, transcribes it with OpenAI Whisper, and generates a warm, context-aware response using GPT.
4. **Manages daily routines** — Tracks scheduled activities (meals, naps, medication) and prompts caregivers when something is overdue.
5. **Displays a caregiver dashboard** — A Next.js web UI gives caregivers a live view of the patient's emotional state, safety status, and recent conversation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        run_live.py                      │
│                     (main entry point)                  │
└───────────────────────┬─────────────────────────────────┘
                        │ events
          ┌─────────────▼──────────────┐
          │       EventBus (queue)     │
          └─────────────┬──────────────┘
                        │
          ┌─────────────▼──────────────┐
          │     BrainOrchestrator      │  ← decision engine
          │   (brain_orchestrator.py)  │
          └──┬──────────┬──────────────┘
             │          │
    ┌────────▼──┐  ┌────▼────────────────┐
    │  LLM      │  │  Interventions      │
    │ Responder │  │  (fall, de-escalate,│
    │ (OpenAI)  │  │   remind, chat)     │
    └───────────┘  └─────────────────────┘

Inputs feeding the EventBus:
  SafetyMonitor      → fall / wandering alerts     (webcam, 12 FPS)
  EmotionMonitor     → emotion updates             (webcam,  2 FPS)
  BrowserMicListener → patient speech transcripts  (microphone)
  TimerTick          → periodic routine checks     (every 20s)
```

---

## Project Structure

```
Capstone_Code/
│
├── src/                            # All Python backend code
│   ├── agent/
│   │   ├── core/
│   │   │   ├── brain_orchestrator.py   # Central decision engine
│   │   │   └── rules.py                # Event types & routing logic
│   │   │
│   │   ├── runtime/
│   │   │   ├── run_live.py             # ← MAIN ENTRY POINT
│   │   │   ├── event_bus.py            # Thread-safe event queue
│   │   │   ├── safety_monitor.py       # Fall & wandering detection loop
│   │   │   ├── emotion_detector.py     # Facial emotion loop (Hume API)
│   │   │   ├── browser_mic_listener.py # Reads transcripts from frontend
│   │   │   ├── ui_state_writer.py      # Writes JSON payload for the UI
│   │   │   ├── latency_logger.py       # Logs response latency to CSV
│   │   │   └── debug_printer.py        # Console logging helpers
│   │   │
│   │   ├── llm/
│   │   │   ├── responder.py            # Calls OpenAI GPT to generate responses
│   │   │   ├── prompt_builder.py       # Builds the system + user prompt
│   │   │   └── protocol_loader.py      # Loads YAML interaction protocols
│   │   │
│   │   ├── perception/vision/
│   │   │   ├── pose_tracker.py         # MediaPipe pose landmark extraction
│   │   │   ├── fall_detector.py        # Fall detection logic
│   │   │   └── presence_detector.py    # Wandering / absence detection
│   │   │
│   │   └── toolsimplementations/
│   │       ├── tools/
│   │       │   ├── hume_http.py                # Hume AI API client (face + voice)
│   │       │   ├── emotion_safety_detector.py  # Maps emotion scores → risk level
│   │       │   ├── conversation_listener.py    # Records mic → Whisper transcript
│   │       │   └── daily_reminder_tool.py      # Checks schedule for overdue tasks
│   │       └── interventions/
│   │           ├── base_intervention.py
│   │           ├── conversation_intervention.py
│   │           ├── de_escalation_intervention.py
│   │           ├── fall_intervention.py
│   │           ├── reminiscence_intervention.py
│   │           └── registry.py                 # Maps ActionType → intervention class
│   │
│   ├── models/
│   │   ├── state.py            # SessionState — tracks all live session data
│   │   ├── decision.py         # ActionType enum & Decision model
│   │   ├── answer.py           # AnswerPayload model
│   │   ├── shared.py           # Shared enums (EmotionLabel, RiskLevel)
│   │   └── tools_schemas/      # Pydantic schemas for tool outputs
│   │
│   └── utils/
│       ├── patient_store.py    # Load/save patient profile JSON
│       ├── caregiver_updates.py# Mark activities as completed
│       └── schedule_utils.py   # Merge routine templates with daily overrides
│
├── frontend/                   # Next.js caregiver + patient UI
│   ├── src/app/
│   │   ├── page.tsx            # Patient-facing avatar dashboard
│   │   ├── caregiver/          # Caregiver monitoring dashboard
│   │   └── api/                # API routes (audio upload, status)
│   └── package.json
│
├── data/
│   ├── patients/
│   │   ├── P001/profile.json   # Patient profile (name, routines, preferences)
│   ├── incoming_transcripts/   # Audio transcripts written by the frontend
│   └── latest_ui_payload.json  # Current UI state (written by backend)
│
├── tests/                       # Pytest test suite
├── test_fall_detector.py         # Standalone webcam fall detection demo
├── test_wandering_detector.py    # Standalone webcam wandering detection demo
├── requirements.txt
├── pyproject.toml
└── .env                         # API keys — DO NOT commit
```

---

## Key Files Explained

| File | Purpose |
|------|---------|
| `src/agent/runtime/run_live.py` | Starts all monitors and runs the main event loop. This is what you run to launch the agent. |
| `src/agent/core/brain_orchestrator.py` | The "brain" — receives events, decides what action to take, and coordinates the response. |
| `src/agent/core/rules.py` | Defines all `EventType` values and the `choose_decision()` logic that maps sensor state to an action. |
| `src/agent/llm/responder.py` | Sends a prompt to OpenAI GPT and returns the agent's spoken response. |
| `src/agent/toolsimplementations/tools/hume_http.py` | Sends image frames or audio bytes to Hume AI and returns emotion confidence scores. |
| `src/models/state.py` | `SessionState` — a single Pydantic model holding everything: emotion history, safety state, current intervention, and conversation log. |
| `data/patients/P001/profile.json` | Patient profile with name, routines, preferences, and caregiver contacts. Edit this to configure a patient. |

---

## Setup & Installation

### Prerequisites

- Python **3.10 or 3.11**
- Node.js **18+** and npm (for the frontend)
- A webcam and microphone
- API keys for OpenAI and Hume AI (see [API Keys](#api-keys--environment-variables) below)

---

### Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd Capstone_Code
```

### Step 2 — Create a Python virtual environment

```bash
python -m venv venv

# Activate it:
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Set up your environment variables

Create a `.env` file in the project root (see the [API Keys](#api-keys--environment-variables) section for what to put in it).

```bash
# Create the file and fill in your keys
touch .env
```

### Step 5 — Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Configuration

### Patient Profile

Each patient has a profile stored at `data/patients/{PATIENT_ID}/profile.json`. Edit this to configure the patient the system will monitor:

```json
{
  "patient_id": "P001",
  "name": "Farah",
  "preferred_language": "english",
  "preferences": "music, church, talking about family",
  "calming_topics": "dancing, food, coffee with neighbors",
  "triggers_to_avoid": "death of loved ones",
  "caregiver_contacts": [],
  "routine_template": {
    "activities": [
      {
        "id": "lunch_time",
        "title": "Lunch Time",
        "time": "12:30",
        "notify_before_min": 5
      }
    ]
  }
}
```

Set the `PATIENT_ID` variable in your `.env` file to match the folder name (e.g., `P001`).

---

## Running the Project

Both the backend and frontend need to be running at the same time. Open two terminal windows.

### Terminal 1 — Start the backend agent

```bash
# From the project root, with your virtual environment activated
cd src
python -m agent.runtime.run_live
```

This starts:
- **Safety monitor** — webcam at 12 FPS for fall and wandering detection
- **Emotion monitor** — webcam at 2 FPS for facial expression analysis via Hume AI
- **Mic listener** — reads transcripts provided by the frontend
- **Brain event loop** — processes all events and generates responses

### Terminal 2 — Start the frontend

```bash
cd frontend
npm run dev
```

Then open your browser to [http://localhost:3000](http://localhost:3000).

- **`/`** — Patient-facing avatar that speaks the agent's responses aloud
- **`/caregiver`** — Caregiver dashboard showing emotion state, safety alerts, and activity reminders

---

### Standalone Vision Demos (no API keys needed)

These let you test the camera pipeline on its own, without running the full system:

```bash
# Shows a live webcam feed with pose overlay and fall detection
python test_fall_detector.py

# Shows a live webcam feed with wandering / absence detection
python test_wandering_detector.py
```

Press `Q` to close the demo window.

---

## Running Tests

```bash
# Run all tests from the project root
pytest tests/

# Run a specific test with verbose output
pytest tests/test_reminders.py -v
```

---

## API Keys & Environment Variables

Create a `.env` file in the **project root** with the following:

```env
# Required — OpenAI (GPT for responses + Whisper for speech transcription)
OPENAI_API_KEY=sk-proj-...

# Required — Hume AI (facial and vocal emotion detection)
HUME_API_KEY=...

# The patient profile to load (matches folder name under data/patients/)
PATIENT_ID=P001
```

Create a `frontend/.env.local` file for the frontend:

```env
OPENAI_API_KEY=sk-proj-...
NEXT_PUBLIC_SIMLI_API_KEY=...     # Optional: enables the animated avatar
```

> **Important:** Never commit `.env` or `.env.local` to version control. Both files are already listed in `.gitignore`.

### Where to get your API keys

| Key | Link |
|-----|------|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `HUME_API_KEY` | [platform.hume.ai](https://platform.hume.ai) |
| `NEXT_PUBLIC_SIMLI_API_KEY` | [simli.com](https://simli.com) — optional, only needed for the avatar |
# memora_v1
