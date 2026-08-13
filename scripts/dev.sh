#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi

# seed on first API boot
(
  cd "$ROOT/backend"
  export PYTHONPATH="$ROOT/backend"
  .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &
BACK_PID=$!

(
  cd "$ROOT/frontend"
  npm run dev -- --host 127.0.0.1 --port 5173
) &
FRONT_PID=$!

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null || true' EXIT
echo "Backend http://127.0.0.1:8000"
echo "Frontend http://127.0.0.1:5173"
wait
