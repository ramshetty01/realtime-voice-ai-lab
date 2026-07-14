# Realtime Voice AI Reliability Lab PRD

## 1. Summary

Realtime Voice AI Reliability Lab is a production-style voice AI system that runs on a free/local stack. It captures microphone audio in the browser, streams it to a backend over WebSockets, transcribes speech, generates an LLM response, synthesizes speech, plays the response back, and records detailed latency metrics for every request.

The project is designed as a portfolio-grade engineering demo, not a paid SaaS product. The goal is to prove realtime multimodal system design, latency analysis, resilience, replay debugging, and clean production habits without depending on paid APIs.

## 2. Problem

Most voice assistant demos only show the happy path: user speaks, model replies. They usually hide the hard parts that matter in real systems:

- where latency is introduced
- what happens when a model or service times out
- how failures are surfaced to the user
- how conversations can be replayed for debugging
- how engineers inspect request-level performance

This project makes those parts visible.

## 3. Goals

- Build an end-to-end realtime voice pipeline.
- Use free/local components where possible.
- Measure latency across ASR, LLM, TTS, and orchestration overhead.
- Provide graceful behavior when one stage fails.
- Support replay mode for debugging recorded inputs.
- Package the system so another engineer can run it locally.
- Present the project clearly in a portfolio, GitHub README, and demo video.

## 4. Non-Goals

- No paid API dependency for the default implementation.
- No multi-tenant SaaS platform.
- No user accounts or billing.
- No mobile app.
- No custom model training in the first version.
- No hand-built observability platform beyond the metrics needed for this demo.

## 5. Target Users

### Primary User

An interviewer, recruiter, or engineering reviewer evaluating the developer's ability to build realtime AI systems.

### Secondary User

The developer using the app to test voice AI latency, failure handling, and local model performance.

## 6. Core Use Cases

### Use Case 1: Voice Conversation

The user opens the web app, clicks record, speaks a question, and receives a spoken AI response.

### Use Case 2: Latency Inspection

After each request, the user sees a breakdown of where time was spent:

- ASR latency
- LLM time to first token
- LLM total time
- TTS time to first byte
- TTS total time
- orchestration overhead
- total response time

### Use Case 3: Failure Handling

If ASR, LLM, or TTS fails or times out, the system returns a useful fallback instead of hanging silently.

### Use Case 4: Replay Debugging

The user can replay saved audio or transcript input through the pipeline and compare outputs and latency.

## 7. Product Requirements

### 7.1 Browser Client

- User can start and stop microphone recording.
- Audio is sent to the backend through a WebSocket.
- User sees live request state: listening, transcribing, thinking, speaking, failed.
- User sees transcript text after ASR completes.
- User sees assistant response text.
- User hears synthesized audio response.
- User sees latency breakdown for the latest request.
- User can inspect recent request history.

### 7.2 Backend API

- Backend exposes a health endpoint.
- Backend exposes a WebSocket endpoint for realtime voice requests.
- Backend assigns a unique request ID to each request.
- Backend emits structured events for each pipeline stage.
- Backend records timing data for each stage.
- Backend stores request metadata locally.
- Backend returns clean error events when a stage fails.

### 7.3 ASR

- Default ASR uses a free/local option such as `faster-whisper` or `whisper.cpp`.
- ASR accepts recorded audio and returns text.
- ASR timeout is enforced.
- ASR errors are recorded with request ID and stage name.

### 7.4 LLM

- Default LLM uses a local Ollama model.
- LLM receives the transcript and returns an assistant response.
- LLM time to first token is measured when streaming is available.
- LLM timeout is enforced.
- If the LLM fails, the system returns a fallback message.

### 7.5 TTS

- Default TTS uses a free/local option such as Piper TTS.
- TTS converts the assistant text into playable audio.
- TTS time to first byte is measured where possible.
- TTS timeout is enforced.
- If TTS fails, the user still sees the text response.

### 7.6 Latency Dashboard

- Dashboard shows latest request latency breakdown.
- Dashboard shows recent requests in a table.
- Dashboard highlights the slowest stage.
- Dashboard displays total response time.
- Dashboard can be implemented with simple frontend charts; no heavy analytics stack is required.

### 7.7 Replay Mode

- System can save request inputs and outputs locally.
- User can replay a saved transcript through the LLM and TTS stages.
- User can replay saved audio through the full pipeline when audio storage is enabled.
- Replay output includes a new latency trace.

### 7.8 Resilience

- Every external or model stage has a timeout.
- Backend does not block indefinitely.
- Errors include request ID, stage, message, and timestamp.
- User-facing errors are short and understandable.
- Internal logs keep enough detail for debugging.

## 8. Event Contract

All WebSocket messages use structured JSON events.

```json
{
  "request_id": "req_123",
  "type": "stage_started",
  "stage": "asr",
  "timestamp": "2026-07-14T16:30:00Z"
}
```

Core event types:

- `request_started`
- `stage_started`
- `stage_completed`
- `partial_transcript`
- `transcript_completed`
- `llm_token`
- `llm_completed`
- `tts_audio_chunk`
- `tts_completed`
- `request_completed`
- `request_failed`

## 9. Latency Metrics

Each request stores:

```json
{
  "request_id": "req_123",
  "asr_ms": 320,
  "llm_ttft_ms": 410,
  "llm_total_ms": 900,
  "tts_ttfb_ms": 280,
  "tts_total_ms": 650,
  "overhead_ms": 120,
  "total_ms": 1990
}
```

## 10. Technical Architecture

```txt
Browser microphone
  -> WebSocket
  -> FastAPI backend
  -> local ASR
  -> local LLM via Ollama
  -> local TTS
  -> WebSocket audio response
  -> Browser playback
```

## 11. Proposed Stack

- Frontend: Next.js
- Backend: FastAPI
- Realtime transport: WebSockets
- ASR: faster-whisper or whisper.cpp
- LLM: Ollama
- TTS: Piper TTS
- Storage: SQLite
- Logging: JSON logs
- Packaging: Docker Compose

## 12. Milestones

### Milestone 1: End-to-End Pipeline

Acceptance criteria:

- User can record audio in the browser.
- Backend receives audio.
- ASR returns transcript.
- LLM returns response.
- TTS returns audio.
- Browser plays audio.

### Milestone 2: Latency Tracking

Acceptance criteria:

- Every request gets a request ID.
- Stage timings are recorded.
- UI shows latest latency breakdown.
- Backend logs structured timing data.

### Milestone 3: Resilience

Acceptance criteria:

- ASR, LLM, and TTS have timeouts.
- Failures return clean WebSocket events.
- TTS failure still returns text.
- LLM failure returns a fallback message.

### Milestone 4: Replay Mode

Acceptance criteria:

- Recent requests are saved locally.
- User can replay a transcript.
- Replay generates a new trace.
- Replay result can be compared with the original request.

### Milestone 5: Portfolio Polish

Acceptance criteria:

- README explains architecture.
- Screenshots show the app and dashboard.
- Demo video shows a live request and latency breakdown.
- Repo includes setup instructions.

## 13. Success Metrics

- End-to-end voice response works locally.
- Median local response time is measured and documented.
- Latency breakdown is visible per request.
- At least three failure modes are handled.
- Replay mode works for at least transcript-based replay.
- A reviewer can run the project from the README.

## 14. Risks

- Local ASR, LLM, and TTS may be slower than paid APIs.
- Audio streaming can become complex if optimized too early.
- Local model setup may vary by machine.
- Browser microphone permissions can introduce setup friction.

## 15. Risk Mitigations

- Start with recorded audio chunks before optimizing true streaming.
- Use Docker Compose where practical.
- Keep `.env.example` clear.
- Document model download commands.
- Make paid API adapters optional future work, not part of the default path.

## 16. Future Enhancements

- Optional Deepgram ASR adapter.
- Optional OpenAI-compatible LLM adapter.
- Optional Cartesia or ElevenLabs TTS adapter.
- VAD-based turn detection.
- Barge-in support.
- Multi-language support.
- Prometheus/Grafana export.
- Load testing script.

## 17. Portfolio Story

This project demonstrates:

- realtime AI orchestration
- multimodal input and output
- WebSocket event design
- local model integration
- latency budgeting
- graceful degradation
- debugging and replay workflows
- production-minded engineering without paid infrastructure

The strongest portfolio claim:

> I built a local-first realtime voice AI system, measured the latency budget across ASR, LLM, and TTS, and added resilience and replay debugging so failures are observable instead of silent.
