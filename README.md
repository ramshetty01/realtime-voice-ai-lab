# Realtime Voice AI Reliability Lab

Production-style local voice AI lab for streaming audio, local ASR/LLM/TTS, latency tracking, replay debugging, and failure handling.

## Project Layout

```txt
backend/   FastAPI service
frontend/  Next.js app
docs/      Product and implementation docs
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

The full product spec is in [docs/PRD.md](docs/PRD.md).
