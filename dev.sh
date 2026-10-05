#!/usr/bin/env bash
# Start backend (FastAPI :8000) and frontend (Vite :5173) together. Ctrl-C stops both.
#   ./dev.sh                          # fast lane: Claude vision OCR
#   BRIEFKLAR_EXTRACTOR=local ./dev.sh   # on-device GLM-OCR
set -euo pipefail
cd "$(dirname "$0")"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set; /analyze (and Claude OCR) will fail." >&2
fi

uv sync -q
[[ -d frontend/node_modules ]] || (cd frontend && npm install)

trap 'kill 0' EXIT
uv run uvicorn api:app --host 127.0.0.1 --port 8000 &
(cd frontend && npm run dev) &
wait
