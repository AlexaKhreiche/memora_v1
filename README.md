# Memora — ADRD Care Assistant

A capstone prototype for supporting people with Alzheimer's Disease and Related Dementias (ADRD). Memora combines camera-based safety monitoring, local facial and speech-expression analysis, patient conversation, and a caregiver dashboard.

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running the app](#running-the-app)
- [Emotion detection](#emotion-detection)
- [Intervention mapping](#intervention-mapping)
- [Terminal output and troubleshooting](#terminal-output-and-troubleshooting)
- [Key files](#key-files)
- [Validation](#validation)

## Features

- Webcam-based fall and wandering/absence monitoring using MediaPipe and OpenCV.
- Local facial-expression classification using a Vision Transformer (ViT), with DeepFace available for comparison.
- Local English speech-emotion classification, combined with fresh facial scores.
- Browser microphone recording, OpenAI Whisper transcription, and GPT-generated responses.
- Simli animated avatar with OpenAI text-to-speech.
- Conversation, reminiscence, and de-escalation interventions, plus safety protocols and caregiver reminders.
- Patient and caregiver views with session state, alerts, routines, and conversation history.

Expression scores and intervention rules are prototype heuristics. They are not calibrated certainty about a person's internal emotional state or clinically validated treatment decisions.

## Architecture

```text
Browser microphone
  ├─ /api/whisper → OpenAI transcription
  └─ accepted transcript + audio → /api/patient-message
       → local transcript queue → BrowserMicListener
          ├─ PATIENT_MESSAGE → EventBus
          └─ VoiceEmotion background worker → recent voice scores

Webcam → face detection/cropping → ViT classifier
                                   + recent voice scores
                                   → EmotionMonitor → EMOTION_UPDATE
Webcam → SafetyMonitor → SENSOR_ALERT
Timer → routine checks

EventBus → BrainOrchestrator → intervention + OpenAI response
                           → JSON UI state → Next.js dashboards
                                           → OpenAI TTS → Simli avatar
```

Face and voice model construction is serialized with a shared lock. Loaded parameters and buffers are checked for unresolved `meta` tensors before the models are placed on the CPU. Inference runs locally after model downloads.

## Setup

The development setup uses macOS and Python 3.11. Other platforms have not been validated with this dependency set.

Requirements:

- Python **3.11** for the installed TensorFlow/DeepFace stack.
- Node.js **20.9 or newer**, as required by the installed Next.js version, and npm.
- Webcam, microphone, and browser camera/microphone permissions.
- Internet access for initial model downloads and the OpenAI/Simli services.
- OpenAI API key; Simli API key for the animated avatar.

From your cloned repository's root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

PyTorch, Transformers, TensorFlow, and model weights require substantial download and disk space. The speech decoder is supplied by `imageio-ffmpeg`.

## Configuration

Create `.env` in the repository root:

```env
OPENAI_API_KEY=your_openai_api_key

# 1 = facial + speech emotion; 0 = speech emotion only
FACIAL_EMOTION_ENABLED=1

# vit (default) or deepface
FACE_EMOTION_BACKEND=vit

# 0 = compact terminal output; 1 = detailed diagnostics
MEMORA_VERBOSE=0
```

Create `frontend/.env.local`:

```env
OPENAI_API_KEY=your_openai_api_key
NEXT_PUBLIC_SIMLI_API_KEY=your_simli_api_key
```

No Hume key is required by the live emotion pipeline. The older Hume client remains in the source tree but is not used by `run_live.py`.

The avatar face ID is configured as `SIMLI_FACE_ID` in `frontend/src/components/CapstoneAvatarBridge.tsx`. Restart the relevant process after changing environment settings. The backend loads `.env` with `override=True`, so values in that file take precedence over shell environment values.

API key portals: [OpenAI](https://platform.openai.com/api-keys), [Simli](https://www.simli.com/).

### Patient profile and local data

The live entry point currently selects **P001** in `src/agent/runtime/run_live.py`; it does not read a `PATIENT_ID` environment variable. Patient details and routines are stored in `data/patients/P001/profile.json` and its associated daily files. The caregiver interface also provides profile editing.

The frontend writes accepted utterances, including base64 audio, to `data/incoming_transcripts/`. The backend deletes each file after consuming it; failed or unprocessed messages can remain on disk. This queue, `.venv`, and environment files are ignored by git. Runtime UI state and other patient files may still be tracked: review your diff before publishing and use demo data in a public repository.

## Running the app

Open two terminals. Run these commands from the repository root.

**Backend:**

```bash
source .venv/bin/activate
PYTHONPATH=src python -m agent.runtime.run_live
```

If your terminal is already inside `src`, use:

```bash
../.venv/bin/python -m agent.runtime.run_live
```

**Frontend:**

```bash
cd frontend
npm run dev
```

Visit [localhost:3000](http://localhost:3000) for the patient avatar and [localhost:3000/caregiver](http://localhost:3000/caregiver) for the caregiver dashboard. Start the avatar session and permit microphone access to provide speech input. Stop the backend with `Ctrl+C`.

The safety loop targets 12 FPS and the facial loop targets 2 FPS; actual throughput depends on hardware and inference time. Emotion events are published approximately once per second. Routine checks run every 20 seconds.

## Emotion detection

### Face

The default classifier is [dima806/facial_emotions_image_detection](https://huggingface.co/dima806/facial_emotions_image_detection). DeepFace supplies OpenCV face detection and alignment; the RGB face crop goes through the ViT image processor and classifier.

- Seven raw labels: happy, sad, neutral, angry, disgust, fear, and surprise.
- Exactly one detected face is required. No face or multiple faces produce no facial scores.
- `FACE_EMOTION_BACKEND=deepface` selects the previous DeepFace expression classifier for comparison.
- Hugging Face weights download on first use and are cached locally. The optional DeepFace expression weights use `~/.deepface/weights`.

Changing classifiers does not guarantee improved webcam accuracy. Compare raw face-only readings on the same lighting, camera position, and expressions.

### Speech

The background worker uses [superb/wav2vec2-base-superb-er](https://huggingface.co/superb/wav2vec2-base-superb-er), analyzing audio rather than the transcript's meaning.

- Supported language: English (`en` or `english`).
- Labels: neutral, happy, angry, and sad.
- Audio is submitted after the existing browser echo and duplicate-transcript filters.
- Audio is decoded locally to 16 kHz mono; analysis is capped at 15 seconds.
- Clips shorter than one second, near-silence, and predictions whose top score is below 0.5 are skipped.
- A bounded queue keeps the latest pending utterance. Transcription and conversation are not blocked by model inference.

### Fusion and speech-only mode

Fresh voice and facial scores are blended equally (50/50). If only one source is available, its scores are used alone. Voice scores expire ten seconds after submission to the worker, including time spent waiting and running inference. A new submitted utterance clears the previous voice scores.

Set `FACIAL_EMOTION_ENABLED=0` in `.env` and restart to test speech alone. This skips the facial model and its camera capture, while the separate fall/wandering monitor remains active. Set it back to `1` to restore combined emotion detection.

Absent usable scores produce `uncertain` at zero confidence. The existing four-second emotion history selects a confidence-weighted winning label, with average confidence among that label's readings. The additional three-second switching delay tested during development is not enabled.

## Intervention mapping

| Detector label | App emotion | Mapped intervention |
| --- | --- | --- |
| Happy | Happy | Conversation |
| Sad | Sad | Reminiscence |
| Neutral | Neutral | Reminiscence |
| Angry or disgust | Agitated | De-escalation |
| Fear | Distressed | De-escalation |
| Surprise | Uncertain | Conversation |
| No usable scores | Uncertain, 0% | Default conversation |

The rules also support calm → reminiscence, anxious → de-escalation, and confused → conversation. The current face and voice models do not directly produce those three labels. Mapping fear to distressed or anger to agitated is an application choice, not an additional model inference.

Actual selection also uses confidence, duration, and session state. Safety events and caregiver reminders take priority. A printed individual emotion reading does not necessarily represent the stabilized emotion used for intervention selection.

## Terminal output and troubleshooting

Compact logging is the default:

```text
EMOTION | happy (72%) | source=face+voice
INTERVENTION | conversation
💬 PATIENT (lang=english, conf=1.00) | Hello Maria.
🤖 AVATAR [intervention=conversation] | Hello! How are you today?
SAFETY | active=no | fall=False | wandering=False
```

Emotion lines repeat when the label, source, or ten-percentage-point score bucket changes. Intervention and safety status print on changes; every avatar reply includes its active intervention. Patient and avatar text is not truncated. The speech text is the backend response sent for playback, not confirmation that the browser played it.

Errors remain visible. Set `MEMORA_VERBOSE=1` in `.env` and restart for internal model diagnostics, full UI payloads, and terminal latency logs. CSV latency recording remains enabled in compact mode.

| Symptom | What to check |
| --- | --- |
| `No module named 'agent'` | From the root, include `PYTHONPATH=src`; alternatively run inside `src`. |
| `.venv/bin/python: no such file` | Inside `src`, use `../.venv/bin/python`. |
| Facial classifier disabled/import error | Use the project `.venv`, install `requirements.txt`, and restart after code updates. |
| Repeated `meta`/CPU tensor errors | Confirm both models use the shared loader in `model_loading.py`; restart to discard previously loaded models. |
| `uncertain (0%)` | No usable scores. Enable verbose output to distinguish initialization errors, inference errors, and missing/multiple faces. |
| Only `source=face` | Voice may be skipped, unavailable, or expired. Check verbose `[VoiceEmotion]` messages immediately after an English utterance. |
| `source=voice` | Voice scores contributed without usable facial scores, or speech-only mode is enabled. |
| `source=face+voice` | Both signals contributed to that reading. |

Third-party libraries may still print startup/download messages or deprecation warnings, including MediaPipe's `SymbolDatabase.GetPrototype()` warning. That warning alone does not indicate failed emotion inference.

## Key files

| File | Purpose |
| --- | --- |
| `src/agent/runtime/run_live.py` | Starts monitors, the timer, and event processing. |
| `src/agent/runtime/emotion_detector.py` | Face capture, face/voice fusion, and emotion events. |
| `src/agent/runtime/voice_emotion.py` | Audio decoding, local speech inference, score expiry, and fusion. |
| `src/agent/runtime/model_loading.py` | Shared model-construction lock and CPU tensor validation. |
| `src/agent/toolsimplementations/tools/vit_face_client.py` | Default ViT facial classifier. |
| `src/agent/toolsimplementations/tools/deepface_client.py` | Alternative DeepFace expression classifier. |
| `src/agent/toolsimplementations/tools/emotion_safety_detector.py` | Expression-to-app-label mapping and risk heuristics. |
| `src/agent/core/rules.py` | Event definitions and intervention rules. |
| `src/agent/core/brain_orchestrator.py` | Session history, decisions, interventions, and UI state. |
| `src/agent/runtime/debug_printer.py` | Compact live terminal output. |
| `frontend/src/components/CapstoneAvatarBridge.tsx` | Avatar, microphone capture, and utterance submission. |
| `frontend/src/app/api/patient-message/route.ts` | Atomic local transcript/audio queue writes. |
| `frontend/src/app/api/whisper/route.ts` | OpenAI speech transcription. |
| `frontend/src/app/api/avatar-tts/route.ts` | OpenAI speech synthesis. |
| `data/latest_ui_payload.json` | Runtime state consumed by the frontend. |

## Validation

From the repository root:

```bash
# Focused local emotion tests
.venv/bin/python -m pytest tests/test_local_emotions.py tests/test_voice_emotion.py tests/test_vit_face.py tests/test_speech_only.py -q

# Other project tests
.venv/bin/python -m pytest tests/

# Frontend type check
cd frontend
npx tsc --noEmit
```

Focused tests cover score conversion, missing/multiple faces, mapping, voice expiry, queue behavior, preprocessing, and speech-only camera bypass. Synthetic inference checks performed during integration confirmed that the actual face and voice weights could load and run on CPU together. These checks do not establish accuracy on real patient recordings; live microphone, webcam, and avatar behavior need manual evaluation.
