#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi

if command -v uv >/dev/null 2>&1; then
  (cd backend && uv sync)
else
  python3 -m venv backend/.venv
  backend/.venv/bin/python -m pip install -e backend
fi

(cd frontend && npm install)

echo "Setup complete. Fill .env keys, then run backend and frontend."
