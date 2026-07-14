# Demo Checklist

## Screenshots

- Main voice request screen connected to the backend.
- Completed request with transcript and assistant response.
- Latency dashboard showing stage timings and slowest stage.
- Recent requests table with replay buttons.
- Failure or degraded response state.

## Demo Script

1. Start backend and frontend.
2. Click `Start` and allow microphone access.
3. Speak a short question.
4. Click `Stop`.
5. Show transcript and assistant response.
6. Play the generated audio.
7. Show latency metrics and slowest stage.
8. Refresh recent requests.
9. Replay a transcript.
10. Explain that local Ollama/Piper are optional and fallback paths keep the pipeline debuggable.

## Portfolio Summary

Built a local-first realtime voice AI system with browser microphone capture, FastAPI WebSockets, local ASR/LLM/TTS adapters, SQLite request traces, latency breakdowns, replay debugging, structured logs, and graceful fallback behavior.

## Benchmark Template

| Machine | ASR Model | LLM Model | TTS Model | Median ASR | Median LLM | Median TTS | Median Total |
|---|---|---|---|---:|---:|---:|---:|
| Local dev | fallback | Ollama fallback | WAV fallback | TBD | TBD | TBD | TBD |
