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
  -> NVIDIA NIM or Ollama LLM adapter
  -> Piper TTS adapter
  -> browser audio playback
  -> SQLite trace + latency metrics
```

This project implements a chained ASR -> LLM -> TTS voice assistant. That is
the right shape for a portfolio reliability lab because each stage can be
measured, replayed, timed out, and swapped independently.

True speech-to-speech realtime voice is different: one live session accepts
audio and returns audio directly, usually over WebRTC. That path can support
lower latency and interruption, but it needs a realtime audio model/provider
rather than the current separate NIM chat-completions, ASR, and TTS adapters.

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
- LLM calls NVIDIA NIM when `NVIDIA_NIM_BASE_URL`, `NVIDIA_NIM_MODEL`, and `NVIDIA_NIM_API_KEY` or `NGC_API_KEY` are set. Otherwise it falls back to Ollama at `OLLAMA_BASE_URL`; if Ollama is unavailable, the app returns a clear fallback response.
- TTS calls Piper when `PIPER_BIN` and `PIPER_MODEL_PATH` are valid; otherwise it returns a short playable WAV fallback.
- Conversation history keeps the latest `MAX_HISTORY_TURNS` turns by default.

Optional local NVIDIA NIM:

```sh
export NGC_API_KEY=<PASTE_API_KEY_HERE>
export LOCAL_NIM_CACHE=~/.cache/nim
mkdir -p "$LOCAL_NIM_CACHE"
chmod -R a+w "$LOCAL_NIM_CACHE"
docker run -it --rm \
  --gpus all \
  --ipc host \
  --shm-size=32GB \
  -e NGC_API_KEY \
  -v "$LOCAL_NIM_CACHE:/opt/nim/.cache" \
  -p 8001:8000 \
  nvcr.io/nim/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:latest
```

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

Portfolio demo mode is local-only for now because the full voice loop depends
on local model runtimes: NVIDIA NIM or Ollama for LLM, faster-whisper for ASR,
and Piper for TTS. Run both services locally:

```sh
cd backend
set -a; source ../.env; set +a
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
cd frontend
set -a; source ../.env; set +a
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Then open http://127.0.0.1:3000.

The full product spec is in [docs/PRD.md](docs/PRD.md).

The lower-latency voice spike is in [docs/REALTIME_SPIKE.md](docs/REALTIME_SPIKE.md).

Current local validation notes are in [docs/VALIDATION.md](docs/VALIDATION.md).

Public demo safeguards are in [docs/PUBLIC_DEMO.md](docs/PUBLIC_DEMO.md).

Local ASR/TTS setup notes are in [docs/LOCAL_MODELS.md](docs/LOCAL_MODELS.md).
