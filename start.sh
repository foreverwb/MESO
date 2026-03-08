#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/.run"
API_DIR="$ROOT_DIR/apps/api"
WEB_DIR="$ROOT_DIR/apps/web"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-18000}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
WEB_PORT="${WEB_PORT:-5174}"

API_LOG="$LOG_DIR/api.log"
WEB_LOG="$LOG_DIR/web.log"

mkdir -p "$LOG_DIR"
: > "$API_LOG"
: > "$WEB_LOG"

resolve_python() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
    return
  fi

  if [[ -x "$API_DIR/.venv/bin/python" ]]; then
    echo "$API_DIR/.venv/bin/python"
    return
  fi

  if command -v python3.11 >/dev/null 2>&1; then
    command -v python3.11
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi

  echo "No Python interpreter was found. Install Python 3.11+ first." >&2
  exit 1
}

cleanup() {
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" >/dev/null 2>&1; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "${WEB_PID:-}" ]] && kill -0 "$WEB_PID" >/dev/null 2>&1; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
}

PYTHON_BIN="$(resolve_python)"

if ! "$PYTHON_BIN" -c "import uvicorn" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
The selected Python environment does not contain uvicorn.

Install backend dependencies first, for example:
  source .venv/bin/activate
  cd apps/api
  python -m pip install -e .[dev]
EOF
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm was not found. Install Node.js and npm first." >&2
  exit 1
fi

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies into apps/web/node_modules ..."
  (
    cd "$WEB_DIR"
    npm install --no-package-lock
  )
fi

trap cleanup EXIT INT TERM

echo "Ensuring backend database schema ..."
(
  cd "$API_DIR"
  "$PYTHON_BIN" -m alembic upgrade head
) >>"$API_LOG" 2>&1

echo "Starting backend on http://$API_HOST:$API_PORT ..."
(
  cd "$API_DIR"
  exec "$PYTHON_BIN" -m uvicorn app.main:app --reload --host "$API_HOST" --port "$API_PORT"
) >>"$API_LOG" 2>&1 &
API_PID=$!

echo "Starting frontend on http://$WEB_HOST:$WEB_PORT ..."
(
  cd "$WEB_DIR"
  exec env VITE_API_BASE_URL="http://$API_HOST:$API_PORT" npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT"
) >>"$WEB_LOG" 2>&1 &
WEB_PID=$!

sleep 2

echo
echo "Services are starting."
echo "  API:       http://$API_HOST:$API_PORT"
echo "  Swagger:   http://$API_HOST:$API_PORT/docs"
echo "  Dashboard: http://$WEB_HOST:$WEB_PORT"
echo "  Logs:      $LOG_DIR"
echo
echo "Press Ctrl+C to stop both services."
echo

tail -f "$API_LOG" "$WEB_LOG"
