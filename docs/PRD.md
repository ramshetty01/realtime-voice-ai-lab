# Realtime Voice AI Reliability Lab PRD

## 1. Executive Summary

Realtime Voice AI Reliability Lab is a local-first, production-style voice AI system for portfolio demonstration. The app records microphone audio in the browser, sends it to a FastAPI backend, transcribes it with local ASR, generates a response with a local LLM, synthesizes speech with local TTS, returns playable audio to the browser, and records a detailed latency trace for every request.

The project is not a paid SaaS product. It is a proof of engineering maturity: realtime orchestration, clean event contracts, stage-level latency budgets, graceful failure handling, replay debugging, and documentation that lets another engineer run and inspect the system.

## 2. Product Name

**Realtime Voice AI Reliability Lab**

Repository name:

```txt
realtime-voice-ai-lab
```

Portfolio subtitle:

```txt
A production-style voice AI system with streaming audio, local ASR/LLM/TTS, latency tracking, replay debugging, and failure handling.
```

## 3. Problem Statement

Most voice assistant demos only prove that a happy path can work once. They rarely show the parts that matter in production:

- where response latency is introduced
- whether the first token arrives quickly enough
- what happens when ASR, LLM, or TTS fails
- whether the user gets feedback instead of silence
- how failed requests are debugged later
- whether engineers can replay a bad input
- how performance claims are measured instead of guessed

This project makes those hidden pieces visible.

## 4. Goals

- Build an end-to-end voice AI pipeline that runs locally.
- Use free/local services by default.
- Support browser microphone input and browser audio playback.
- Use structured WebSocket events for request lifecycle updates.
- Measure latency for ASR, LLM, TTS, orchestration overhead, and total response time.
- Persist request traces for inspection and replay.
- Add timeouts and fallbacks so requests do not hang silently.
- Provide a clear README, architecture explanation, and demo checklist.

## 5. Non-Goals

- No paid API requirement in the default path.
- No multi-tenant deployment.
- No user authentication.
- No billing.
- No mobile app.
- No custom model training.
- No full observability stack such as Prometheus or Grafana in the MVP.
- No guarantee of cloud-grade latency from local models.
- No complex agent framework unless a real use case appears.

## 6. Production-Level Definition

For this portfolio project, "production-level" means production-minded engineering quality, not production-scale infrastructure.

In scope:

- deterministic setup
- clear service boundaries
- request IDs
- structured events
- structured logs
- explicit timeouts
- graceful degradation
- persisted traces
- replay debugging
- documented limitations

Out of scope:

- horizontal scaling
- multi-region availability
- enterprise authentication
- paid managed inference
- high-volume traffic guarantees

## 7. Target Users

### 7.1 Primary User

An interviewer, recruiter, hiring manager, or engineer reviewing the developer's ability to build realtime AI systems.

### 7.2 Secondary User

The developer using the app to test local voice AI performance, inspect latency, and debug failures.

### 7.3 Reviewer Expectations

A reviewer should be able to answer these questions within a few minutes:

- What does the system do?
- How does audio move through the pipeline?
- Where is latency measured?
- What happens when one component fails?
- Can this be run locally?
- What tradeoffs were made to keep it free?

## 8. User Stories

### 8.1 Voice Conversation

As a user, I want to speak into the browser and hear an AI response so that I can test a complete voice assistant loop.

Acceptance criteria:

- User can start recording.
- User can stop recording.
- Browser sends non-empty audio to the backend.
- Backend returns transcript text.
- Backend returns assistant text.
- Browser plays assistant audio.
- UI returns to an idle or ready state after completion.

### 8.2 Realtime Status

As a user, I want to see what stage the request is in so that the app does not feel frozen.

Acceptance criteria:

- UI shows at least these states: idle, recording, transcribing, thinking, speaking, completed, failed.
- State changes are driven by backend events where applicable.
- Failure state includes a short user-facing message.

### 8.3 Latency Inspection

As a reviewer, I want to see the latency breakdown for each request so that performance claims are backed by measurements.

Acceptance criteria:

- Latest request shows stage-level latency.
- Total request time is visible.
- Slowest stage is highlighted.
- Missing values render as unavailable, not zero.

### 8.4 Failure Handling

As a user, I want failures to produce useful output instead of silence.

Acceptance criteria:

- ASR timeout returns a transcription failure.
- LLM timeout returns a fallback response.
- TTS timeout preserves the text response.
- Every failure includes request ID and failed stage in logs.

### 8.5 Replay Debugging

As a developer, I want to replay saved requests so that I can reproduce and compare behavior.

Acceptance criteria:

- A stored transcript can be replayed through LLM and TTS.
- Optional saved audio can be replayed through ASR, LLM, and TTS.
- Replay creates a new trace linked to the original request.

## 9. MVP Scope

The MVP is complete when this works locally:

```txt
Browser mic
  -> backend WebSocket
  -> local ASR
  -> local LLM
  -> local TTS
  -> browser playback
  -> persisted trace
  -> latency dashboard
```

Minimum usable demo:

- one browser page
- one backend service
- one WebSocket pipeline
- one local ASR adapter
- one local LLM adapter
- one local TTS adapter
- SQLite request trace storage
- latest-request latency display
- recent requests table
- transcript replay

## 10. Recommended Free Stack

| Layer | Default Choice | Reason |
|---|---|---|
| Frontend | Next.js | Common portfolio stack, good browser API support |
| Backend | FastAPI | Small async API surface, good WebSocket support |
| Realtime | WebSocket | Native browser support, simple bidirectional events |
| ASR | faster-whisper | Free local transcription with practical quality |
| LLM | Ollama | Local LLM runtime with simple HTTP API |
| TTS | Piper | Free local speech synthesis |
| Storage | SQLite | Enough for local traces and replay |
| Logging | JSON logs | Simple, inspectable, production-like |
| Packaging | Docker Compose | Local reproducibility without cloud cost |

Paid services may be added later as optional adapters, not default requirements.

## 11. System Architecture

```txt
┌────────────────────┐
│ Browser UI          │
│ - microphone        │
│ - status view       │
│ - transcript        │
│ - response text     │
│ - audio playback    │
│ - latency dashboard │
└─────────┬──────────┘
          │ WebSocket events + audio payload
┌─────────▼──────────┐
│ FastAPI Backend     │
│ - request IDs       │
│ - event orchestration│
│ - timing            │
│ - error handling    │
│ - trace storage     │
└────┬────────┬──────┘
     │        │
┌────▼───┐ ┌──▼──────┐ ┌────────┐
│ ASR    │ │ LLM     │ │ TTS    │
│ local  │ │ Ollama  │ │ Piper  │
└────────┘ └─────────┘ └────────┘
          │
┌─────────▼──────────┐
│ SQLite              │
│ request traces      │
│ latency metrics     │
│ replay links        │
└────────────────────┘
```

## 12. Request Lifecycle

1. Browser connects to backend WebSocket.
2. User starts microphone recording.
3. Browser captures audio.
4. User stops recording.
5. Browser sends audio payload metadata and bytes.
6. Backend creates `request_id`.
7. Backend emits `request_started`.
8. Backend runs ASR and emits transcription events.
9. Backend sends transcript to LLM.
10. Backend streams or returns LLM response.
11. Backend sends response text to TTS.
12. Backend returns audio to browser.
13. Browser plays audio.
14. Backend stores trace and metrics.
15. UI updates latency dashboard.

## 13. Functional Requirements

### 13.1 Browser Client

- Must request microphone permission only when the user starts recording.
- Must show permission-denied errors clearly.
- Must support start and stop recording.
- Must prevent starting a second request while one is active.
- Must send audio MIME type, size, and duration if available.
- Must display current request state.
- Must display transcript.
- Must display assistant response text.
- Must play assistant audio when available.
- Must keep text response visible if audio playback fails.
- Must show latest latency metrics.
- Must show recent request history.

### 13.2 Backend API

- Must expose `GET /health`.
- Must expose a voice WebSocket endpoint.
- Must create a unique request ID per request.
- Must validate non-empty audio input.
- Must emit structured JSON events.
- Must time each pipeline stage.
- Must persist completed and failed traces.
- Must avoid logging raw audio bytes.
- Must return clean failure events.

### 13.3 ASR

- Must run with a free/local ASR engine.
- Must accept browser-recorded audio.
- Must return transcript text.
- Must enforce timeout.
- Must record ASR duration.
- Must record ASR error details on failure.

### 13.4 LLM

- Must call a local Ollama model by default.
- Must support configurable model name.
- Must send transcript as the user message.
- Must stream tokens if supported.
- Must measure time to first token.
- Must measure total LLM duration.
- Must enforce timeout.
- Must provide fallback response on timeout or model failure.

### 13.5 TTS

- Must synthesize assistant text into playable audio.
- Must use a free/local TTS engine by default.
- Must support configurable voice/model path.
- Must measure TTS duration.
- Should measure time to first byte if the selected TTS path supports it.
- Must enforce timeout.
- Must preserve text output when audio fails.

### 13.6 Latency Dashboard

- Must display latest request metrics.
- Must display total response time.
- Must display stage durations.
- Must highlight the slowest measured stage.
- Must show failed stages distinctly.
- Should include a compact recent request table.

### 13.7 Replay

- Must support transcript replay.
- Should support audio replay when audio persistence is enabled.
- Must link replay request to original request.
- Must create a new trace for replay results.

## 14. API Endpoints

### 14.1 Health

```txt
GET /health
```

Example response:

```json
{
  "status": "ok",
  "service": "realtime-voice-ai-lab",
  "timestamp": "2026-07-14T16:30:00Z"
}
```

### 14.2 Recent Requests

```txt
GET /requests?limit=20
```

Example response:

```json
{
  "requests": [
    {
      "request_id": "req_01",
      "status": "completed",
      "created_at": "2026-07-14T16:30:00Z",
      "transcript_preview": "What is latency?",
      "total_ms": 1990
    }
  ]
}
```

### 14.3 Request Detail

```txt
GET /requests/{request_id}
```

Returns transcript, response, status, stage metrics, and error details if present.

### 14.4 Replay Transcript

```txt
POST /requests/{request_id}/replay-transcript
```

Creates a new request trace linked to the original request.

### 14.5 Voice WebSocket

```txt
WS /ws/voice
```

Used for request lifecycle events, audio upload, and audio response metadata.

## 15. WebSocket Event Contract

All WebSocket JSON messages must include:

- `type`
- `request_id` when a request exists
- `timestamp`

Base event:

```json
{
  "type": "stage_started",
  "request_id": "req_01",
  "timestamp": "2026-07-14T16:30:00Z",
  "stage": "asr"
}
```

Core event types:

| Event | Direction | Purpose |
|---|---|---|
| `client_audio_ready` | client to server | Announces recorded audio metadata |
| `request_started` | server to client | Request ID created |
| `stage_started` | server to client | Pipeline stage started |
| `stage_completed` | server to client | Pipeline stage completed |
| `transcript_completed` | server to client | Final ASR transcript |
| `llm_token` | server to client | Streamed response token |
| `llm_completed` | server to client | Final response text |
| `tts_audio_ready` | server to client | Audio response is ready |
| `request_completed` | server to client | Full request completed |
| `request_failed` | server to client | Request failed or partially degraded |

Failure event:

```json
{
  "type": "request_failed",
  "request_id": "req_01",
  "timestamp": "2026-07-14T16:30:10Z",
  "stage": "llm",
  "code": "timeout",
  "message": "The local language model timed out.",
  "recoverable": true
}
```

## 16. Latency Metrics

Each request should store these metrics when available:

```json
{
  "request_id": "req_01",
  "asr_ms": 320,
  "llm_ttft_ms": 410,
  "llm_total_ms": 900,
  "tts_ttfb_ms": null,
  "tts_total_ms": 650,
  "overhead_ms": 120,
  "total_ms": 1990,
  "slowest_stage": "llm"
}
```

Metric definitions:

| Metric | Definition |
|---|---|
| `asr_ms` | Time from ASR start to transcript completion |
| `llm_ttft_ms` | Time from LLM request start to first token |
| `llm_total_ms` | Time from LLM request start to final response |
| `tts_ttfb_ms` | Time from TTS start to first audio byte, if available |
| `tts_total_ms` | Time from TTS start to completed audio |
| `overhead_ms` | Total time not attributed to ASR, LLM, or TTS |
| `total_ms` | Time from request start to final completion/failure |

Use monotonic clocks for durations. Use wall-clock timestamps only for display and logs.

## 17. Persistence Model

SQLite is enough for the MVP.

### 17.1 `requests`

| Column | Type | Notes |
|---|---|---|
| `request_id` | text primary key | Server-generated |
| `status` | text | `completed`, `failed`, `degraded`, `replayed` |
| `created_at` | text | ISO timestamp |
| `completed_at` | text nullable | ISO timestamp |
| `transcript` | text nullable | ASR result |
| `assistant_response` | text nullable | LLM result |
| `error_stage` | text nullable | Failed stage |
| `error_code` | text nullable | Machine-readable error |
| `error_message` | text nullable | Debuggable message |
| `replay_of` | text nullable | Original request ID |
| `audio_path` | text nullable | Only when audio persistence is enabled |

### 17.2 `request_metrics`

| Column | Type |
|---|---|
| `request_id` | text primary key |
| `asr_ms` | integer nullable |
| `llm_ttft_ms` | integer nullable |
| `llm_total_ms` | integer nullable |
| `tts_ttfb_ms` | integer nullable |
| `tts_total_ms` | integer nullable |
| `overhead_ms` | integer nullable |
| `total_ms` | integer nullable |
| `slowest_stage` | text nullable |

## 18. Failure Behavior

| Failure | User Behavior | Trace Behavior |
|---|---|---|
| Microphone denied | Show permission message | No backend trace required |
| Empty audio | Show validation error | Failed request with `audio_validation` |
| ASR timeout | Show transcription failed | Failed request with `asr` timeout |
| LLM timeout | Show fallback response | Degraded request with `llm` timeout |
| TTS timeout | Show text response only | Degraded request with `tts` timeout |
| WebSocket disconnect | Show disconnected state | Log disconnect if request exists |
| SQLite write failure | Show request result if possible | Log storage error |

Fallback response for LLM timeout:

```txt
I had trouble generating a full response from the local model. Please try again with a shorter request.
```

## 19. Configuration

Use `.env` with documented defaults.

```txt
APP_ENV=development
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
DATABASE_URL=sqlite:///./data/voice_lab.db
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
ASR_MODEL=base
ASR_TIMEOUT_SECONDS=30
LLM_TIMEOUT_SECONDS=45
TTS_TIMEOUT_SECONDS=30
PIPER_MODEL_PATH=./models/piper/default.onnx
AUDIO_PERSISTENCE_ENABLED=false
```

Do not commit downloaded model files or recorded audio by default.

## 20. Security And Privacy

- Do not log raw audio.
- Do not log full transcripts in error logs unless debug mode is explicit.
- Store audio only when `AUDIO_PERSISTENCE_ENABLED=true`.
- Keep generated local data out of git.
- Validate audio size before processing.
- Limit accepted audio formats to documented browser outputs.
- Avoid exposing the backend publicly without adding authentication and stricter CORS.

## 21. Accessibility

- Recording controls must be keyboard accessible.
- Buttons must have clear accessible labels.
- State changes must be visible as text, not only color.
- Error messages must be readable without audio playback.
- Audio response must have text equivalent through the assistant response.

## 22. Local Development Workflow

Expected reviewer flow:

```txt
git clone <repo>
cd realtime-voice-ai-lab
cp .env.example .env
# install local model prerequisites
# start backend
# start frontend
# open browser app
```

The README must include exact commands once implementation exists.

## 23. Testing Strategy

Keep tests small and tied to real breakage risk.

Required checks:

- health endpoint returns JSON
- event schema validation covers required fields
- timing helper uses monotonic duration
- empty audio validation fails cleanly
- LLM timeout returns fallback
- TTS failure preserves text response
- transcript replay creates a new linked request

Manual demo checks:

- microphone permission allowed path
- microphone permission denied path
- normal voice request
- local LLM unavailable path
- TTS unavailable path
- latency dashboard after completion
- replay from transcript

## 24. Milestones

### Milestone 1: End-to-End Pipeline

Acceptance criteria:

- Frontend starts locally.
- Backend starts locally.
- Browser records audio.
- Backend receives audio.
- ASR returns transcript.
- LLM returns response.
- TTS returns audio.
- Browser plays audio.

### Milestone 2: Latency Tracking

Acceptance criteria:

- Every request has a request ID.
- Stage timings are recorded.
- Latest request metrics display in UI.
- Slowest stage is highlighted.
- JSON logs include request ID and stage timing.

### Milestone 3: Resilience

Acceptance criteria:

- ASR timeout is enforced.
- LLM timeout returns fallback.
- TTS timeout preserves text.
- Failed and degraded requests are persisted.
- UI does not hang silently.

### Milestone 4: Replay Debugging

Acceptance criteria:

- Requests are stored locally.
- Transcript replay works.
- Replay creates a new trace.
- Original and replay request IDs are linked.

### Milestone 5: Portfolio Polish

Acceptance criteria:

- README explains the project and setup.
- Architecture diagram is included.
- Demo checklist is included.
- Screenshots show app, request history, and latency dashboard.
- Benchmark table documents local performance.

## 25. Issue Plan

The project is split into 30 implementation issues:

| Phase | Focus |
|---|---|
| Phase 1 | app shell, WebSocket pipeline, ASR, LLM, TTS |
| Phase 2 | SQLite traces, latency helper, dashboard, request history, logs |
| Phase 3 | ASR/LLM/TTS timeout and fallback behavior |
| Phase 4 | transcript and optional audio replay |
| Phase 5 | Docker, README, portfolio evidence |

Each issue should produce one focused PR where practical.

## 26. Success Metrics

Project success:

- End-to-end voice response works locally.
- A reviewer can run the project from the README.
- Every request has a trace.
- Latency breakdown is visible per request.
- At least three failure modes are demonstrated.
- Transcript replay works.
- Portfolio README includes screenshots or a demo checklist.

Performance reporting:

- Report median total response time from at least 10 local test requests.
- Report median ASR, LLM, and TTS duration separately.
- Document machine specs used for benchmark.
- Document selected ASR, LLM, and TTS models.

## 27. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Local models are slow | Demo feels less realtime | Make latency visible and explain tradeoff |
| Model setup is hard | Reviewer cannot run app | Document exact setup commands |
| Browser audio format varies | ASR may fail | Normalize or document supported formats |
| WebSocket flow gets complex | Bugs spread across frontend/backend | Keep event contract small |
| Audio persistence creates privacy risk | Sensitive local files | Disable by default |

## 28. Future Enhancements

- Optional Deepgram ASR adapter.
- Optional OpenAI-compatible LLM adapter.
- Optional Cartesia or ElevenLabs TTS adapter.
- Voice activity detection.
- Barge-in support.
- Streaming audio chunks instead of recorded blob upload.
- Multi-language support.
- Prometheus/Grafana export.
- Load testing script.
- Cloud deployment profile.

## 29. Portfolio Story

This project demonstrates:

- realtime AI orchestration
- multimodal input and output
- WebSocket event design
- local model integration
- latency budgeting
- graceful degradation
- debugging and replay workflows
- production-minded engineering without paid infrastructure

Strong portfolio claim:

> I built a local-first realtime voice AI system, measured the latency budget across ASR, LLM, and TTS, and added resilience and replay debugging so failures are observable instead of silent.

## 30. Demo Script

1. Open the app.
2. Start recording.
3. Ask a short question.
4. Stop recording.
5. Show transcript.
6. Show streamed or completed assistant response.
7. Play audio response.
8. Point to latency dashboard.
9. Show recent request trace.
10. Replay the transcript.
11. Trigger one failure mode, such as local TTS unavailable.
12. Show graceful fallback and stored failed/degraded trace.

## 31. Open Decisions

These should be finalized during implementation:

- Choose `faster-whisper` or `whisper.cpp` as the first ASR backend.
- Choose default Ollama model based on local machine performance.
- Choose whether audio upload uses binary WebSocket frames or short-lived HTTP upload plus WebSocket events.
- Choose whether generated TTS audio is sent as bytes or served by temporary local URL.

Default to the simplest working option during implementation.
