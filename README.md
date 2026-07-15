# Realtime Voice AI Reliability Lab

Production-style local voice AI lab for browser microphone capture, FastAPI WebSockets, local ASR/LLM/TTS adapters, latency tracking, SQLite traces, replay debugging, and failure handling.

## Project Layout

```txt
backend/   FastAPI service
frontend/  Next.js app
docs/      Product and implementation docs
```

## Architecture

```txt
Browser microphone
  -> WebSocket /ws/voice
  -> audio validation
  -> ASR adapter
  -> Ollama LLM adapter
  -> Piper TTS adapter
  -> browser audio playback
  -> SQLite trace + latency dashboard
```

## Local Setup

```sh
cp .env.example .env
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

```sh
cd frontend
npm install
npm run dev
```

Open:

- Frontend: http://127.0.0.1:3000
- Backend health: http://127.0.0.1:8000/health

## Docker

```sh
cp .env.example .env
docker compose up --build
```

## Local Model Notes

The app stays free by default:

- ASR uses `faster-whisper` when installed; otherwise it falls back to `ASR_TRANSCRIPT_TEXT` or a development transcript.
- LLM calls Ollama at `OLLAMA_BASE_URL`; if Ollama is unavailable, the app returns a clear fallback response.
- TTS calls Piper when `PIPER_BIN` and `PIPER_MODEL_PATH` are valid; otherwise it returns a short playable WAV fallback.

Optional local ASR:

```sh
cd backend
source .venv/bin/activate
pip install faster-whisper
```

Generated data is ignored by git:

- `data/`
- `recordings/`
- `models/`

## Verification

```sh
backend/.venv/bin/pytest
cd frontend
npm run build
```

## Demo

Demo checklist and portfolio copy are in [docs/DEMO.md](docs/DEMO.md).

The full product spec is in [docs/PRD.md](docs/PRD.md).
