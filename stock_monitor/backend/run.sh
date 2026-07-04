#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

MODE="${1:-minimal}"   # "minimal" (default) or "fastapi"

mkdir -p data/captures

# Prefer python3 (common on macOS); fall back to python if needed
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "Error: python3 (or python) not found in PATH. Install Python 3."
  exit 1
fi

if [ "$MODE" = "fastapi" ]; then
  if [ ! -d ".venv" ]; then
    $PY -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
  else
    source .venv/bin/activate
  fi
  echo "Starting FASTAPI backend (heavier) on http://127.0.0.1:8787"
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
else
  echo "Starting MINIMAL JSON receiver (preferred) on http://127.0.0.1:8787"
  echo "Using: $PY"
  echo "Output: data/captures/*.json + candles.ndjson"
  $PY receiver.py
fi

