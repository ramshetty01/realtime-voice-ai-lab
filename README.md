# Realtime Voice AI Reliability Lab

Local voice AI reliability lab for browser microphone capture, FastAPI WebSockets, local ASR/LLM/TTS adapters, latency tracking, SQLite traces, replay debugging, and failure handling.

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

One command:

```sh
./scripts/setup_local.sh
```

Manual setup:

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

## Access controls

Direct local development accepts loopback clients when `VOICE_LOCAL_ONLY=true` and
`VOICE_API_TOKEN` is blank. Shared access requires a private `VOICE_API_TOKEN`; enter
that token in the browser’s **API access** section. It stays in page memory. Do not
enter a model-provider API key there. HTTP requests use bearer authorization and
WebSocket clients authenticate in their first frame, never in a URL. Exact browser
origins are checked for both transports.

Local mode must not be exposed through a reverse proxy. Shared-token mode is for a
single owner/reviewer group, not per-user trace isolation. See [public access notes](docs/PUBLIC_DEMO.md).

## Docker

```sh
cp .env.example .env

# Set VOICE_API_TOKEN to a private value in .env first.
docker compose up --build
```

## Local Model Notes

The app stays free by default:

- ASR uses `faster-whisper` when installed; otherwise it falls back to `ASR_TRANSCRIPT_TEXT` or a development transcript.
- LLM calls NVIDIA NIM when `NVIDIA_NIM_BASE_URL`, `NVIDIA_NIM_MODEL`, and `NVIDIA_NIM_API_KEY` or `NGC_API_KEY` are set. Otherwise it falls back to Ollama at `OLLAMA_BASE_URL`; if Ollama is unavailable, the app returns a clear fallback response.
- TTS calls Piper when `PIPER_BIN` and `PIPER_MODEL_PATH` are valid; otherwise it returns a short playable WAV fallback.
- Conversation history keeps the latest `MAX_HISTORY_TURNS` turns by default.
- Voice uploads larger than `MAX_AUDIO_BYTES` are rejected before ASR.

Frontend env values:

- `NEXT_PUBLIC_API_URL`: HTTP API base URL. Default: `http://127.0.0.1:8000`.
- `NEXT_PUBLIC_VOICE_WS_URL`: voice websocket URL. Default: `ws://127.0.0.1:8000/ws/voice`.
- `NEXT_PUBLIC_SILENCE_THRESHOLD`: auto-stop volume threshold. Default: `0.025`.
- `NEXT_PUBLIC_SILENCE_DURATION_MS`: silence time before auto-stop. Default: `1200`.

Request traces are stored in SQLite at `data/voice_lab.db` by default. Set
`REQUEST_DB_PATH=/path/to/voice_lab.db` to use a different database file.

Voice recordings are not saved unless `AUDIO_PERSISTENCE_ENABLED=true`. When
enabled, recordings are written under `recordings/` for replay debugging.

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

[Project technical brief](docs/PROJECT_BRIEF.md) describes the actual architecture, verified behavior and remaining production blockers.


### Bounded adapter work and truthful output

`VOICE_MAX_WORKERS` sets a per-process limit of 1–8 actual blocking adapter jobs
(default 2). Timed-out or cancelled callers keep their slot occupied until the
underlying worker completes. New HTTP model work receives 429 with Retry-After
when capacity is full; voice sessions receive a failed admission event. Completed
text can remain available when TTS is busy or fails.

Every successful/degraded trace and response records `metrics.adapters`, including
provider, fallback reason and whether the output is development-only. The UI and
trace details expose this information. Simulated transcripts, missing-model replies
and silent audio are marked degraded rather than completed. Set
`VOICE_STRICT_ADAPTERS=true` to withhold these development outputs. A real alternate
provider such as Ollama after configured NVIDIA failure is recorded as an alternate
adapter, not as simulated output; strict mode can still use real alternatives.

This bounds work; it does not forcibly terminate an in-process ASR/model thread,
provide distributed quotas or establish live speech quality. A supervisor/process
isolation design and hardware-based validation remain required for public service.
