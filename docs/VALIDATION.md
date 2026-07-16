# Local Validation

Last run: 2026-07-17

## Passing Checks

```sh
backend/.venv/bin/pytest
```

Result: 18 passed.

```sh
cd frontend
npm run build
```

Result: production build passed.

```sh
curl http://127.0.0.1:8000/health
```

Result: backend returned `status: ok`.

```sh
curl -I http://127.0.0.1:3000
```

Result: frontend returned HTTP 200.

## Demo Status

- Typed chat route works and returns a playable audio URL.
- Conversation history is sent to the backend for typed and voice turns.
- Voice recording supports manual Stop and automatic silence stop.
- Backend gracefully falls back when the configured LLM provider is unavailable.

## Current Blocker

The local NVIDIA NIM verification is not complete on this machine.

- `.env` points `NVIDIA_NIM_BASE_URL` at `http://127.0.0.1:8001/v1`.
- Port `8001` is currently another uvicorn service, not a NIM container.
- Docker is running without an NVIDIA runtime on this macOS ARM machine.
- `nvidia-smi` is unavailable.

To finish NIM validation, run the NIM container on a machine with an NVIDIA GPU
runtime, map it to the configured NIM port, then retry `/chat`.

