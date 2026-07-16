# Demo Checklist

## Screenshots

- Main chat console connected to the backend.
- Typed conversation with assistant response.
- Voice recording state: ready, recording, thinking, speaking.
- Completed voice turn with transcript, assistant response, and audio player.
- Failure or degraded response state when local models are unavailable.

## Demo Script

1. Start backend and frontend.
2. Type a short question in the composer and send it.
3. Show the assistant response and generated audio player.
4. Click `Voice` and allow microphone access.
5. Speak a short question.
6. Let silence detection stop the turn, or click `Stop` manually.
7. Show the transcript and assistant response in the same conversation thread.
8. Explain that backend traces and latency metrics are available through the API.
9. Explain that local NIM/Ollama/Piper are optional and fallback paths keep the pipeline debuggable.

## Portfolio Summary

Built a local-first realtime voice AI system with a ChatGPT-style chat console, browser microphone capture, FastAPI WebSockets, local ASR/LLM/TTS adapters, SQLite request traces, latency breakdowns, replay debugging, structured logs, and graceful fallback behavior.

## Benchmark Template

| Machine | ASR Model | LLM Model | TTS Model | Median ASR | Median LLM | Median TTS | Median Total |
|---|---|---|---|---:|---:|---:|---:|
| Local dev | faster-whisper or fallback | NVIDIA NIM, Ollama, or fallback | Piper or WAV fallback | TBD | TBD | TBD | TBD |
