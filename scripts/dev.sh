#!/bin/bash
# Run backend + frontend together (dev mode). Foreground by default; -d detaches.
#
#   frontend (Vite dev, proxies /api) -> http://HOST:6606
#   backend  (JSON API)                -> http://HOST:6607/api/status
#
# Usage:
#   scripts/dev.sh [-d|--detach] [--times 07:00,18:00] [backend args...] [-- vite args...]
#
#   -d, --detach  run backend + frontend in the background (logs to .logs/,
#                 pids to .pids/). Stop with `scripts/service.sh stop`.
#                 Without -d, both run in the foreground.
#
#   Args before `--` are forwarded to client/backend.py.
#   Args after `--` are forwarded to `npm run dev` (vite).
#   (-d/--detach before `--` is consumed by dev.sh, not forwarded.)
#
# Env overrides: FRONTEND_PORT, BACKEND_PORT, HOST, VITE_API_PROXY
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_PORT="${FRONTEND_PORT:-6606}"
BACKEND_PORT="${BACKEND_PORT:-6607}"
HOST="${HOST:-0.0.0.0}"

BACKEND_ARGS=()
VITE_ARGS=()
SEEN_SEP=0
DETACH=0
for arg in "$@"; do
  if [ "$arg" = "--" ]; then
    SEEN_SEP=1
    continue
  fi
  if [ "$SEEN_SEP" -eq 0 ] && { [ "$arg" = "-d" ] || [ "$arg" = "--detach" ]; }; then
    DETACH=1
    continue
  fi
  if [ "$SEEN_SEP" -eq 0 ]; then
    BACKEND_ARGS+=("$arg")
  else
    VITE_ARGS+=("$arg")
  fi
done

command -v python3 >/dev/null || { echo "error: python3 not found" >&2; exit 1; }
command -v npm >/dev/null || { echo "error: npm not found (nodejs required)" >&2; exit 1; }
[ -f "$ROOT/client/backend.py" ] || { echo "error: client/backend.py not found" >&2; exit 1; }
[ -f "$ROOT/client/frontend/package.json" ] || { echo "error: client/frontend/package.json not found" >&2; exit 1; }

if [ ! -d "$ROOT/client/frontend/node_modules" ]; then
  echo "Installing frontend deps..."
  (cd "$ROOT/client/frontend" && npm install --no-audit --no-fund)
fi

port_busy() {
  python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.5); sys.exit(0 if s.connect_ex(('$HOST',$1))==0 else 1)" 2>/dev/null
}
if port_busy "$BACKEND_PORT"; then
  echo "error: backend port $BACKEND_PORT on $HOST is busy. Stop it first (scripts/service.sh stop) or set BACKEND_PORT." >&2
  exit 1
fi
if port_busy "$FRONTEND_PORT"; then
  echo "error: frontend port $FRONTEND_PORT on $HOST is busy. Stop it first (scripts/service.sh stop) or set FRONTEND_PORT." >&2
  exit 1
fi

BACKEND_PID=""
FRONTEND_PID=""
PID_DIR="$ROOT/.pids"
LOG_DIR="$ROOT/.logs"
BACKEND_PIDFILE="$PID_DIR/backend.pid"
FRONTEND_PIDFILE="$PID_DIR/frontend.pid"

alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

if [ "$DETACH" -eq 1 ]; then
  mkdir -p "$PID_DIR" "$LOG_DIR"
  if alive "$BACKEND_PIDFILE" || alive "$FRONTEND_PIDFILE"; then
    echo "error: already running (see .pids/). Use 'scripts/service.sh stop' first." >&2
    exit 1
  fi
  # Stale pidfiles from a crash: drop them so a fresh start works.
  rm -f "$BACKEND_PIDFILE" "$FRONTEND_PIDFILE"

  echo "Starting backend (detached)  -> http://$HOST:$BACKEND_PORT/api/status"
  # shellcheck disable=SC2086
  nohup python3 "$ROOT/client/backend.py" --host "$HOST" --port "$BACKEND_PORT" ${BACKEND_ARGS[@]+"${BACKEND_ARGS[@]}"} \
    >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$BACKEND_PIDFILE"

  sleep 1
  if ! alive "$BACKEND_PIDFILE"; then
    echo "error: backend exited on startup. See $LOG_DIR/backend.log" >&2
    rm -f "$BACKEND_PIDFILE"
    exit 1
  fi

  echo "Starting frontend (detached) -> http://$HOST:$FRONTEND_PORT"
  export VITE_API_PROXY="${VITE_API_PROXY:-http://$HOST:$BACKEND_PORT}"
  # exec vite directly (not via npm) so the pidfile holds the server pid
  # itself and `scripts/service.sh stop` (plain kill) actually frees the port.
  # shellcheck disable=SC2086
  nohup bash -c 'cd "$1" && _HOST="$2" && _PORT="$3" && shift 3 && if [ -x ./node_modules/.bin/vite ]; then exec ./node_modules/.bin/vite --host "$_HOST" --port "$_PORT" --strictPort "$@"; else exec npm run dev -- --host "$_HOST" --port "$_PORT" --strictPort "$@"; fi' \
    _ "$ROOT/client/frontend" "$HOST" "$FRONTEND_PORT" ${VITE_ARGS[@]+"${VITE_ARGS[@]}"} \
    >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$FRONTEND_PIDFILE"

  sleep 2
  if ! alive "$FRONTEND_PIDFILE"; then
    echo "error: frontend exited on startup. See $LOG_DIR/frontend.log" >&2
    kill "$(cat "$BACKEND_PIDFILE")" 2>/dev/null || true
    rm -f "$BACKEND_PIDFILE" "$FRONTEND_PIDFILE"
    exit 1
  fi

  echo "Detached. Logs: $LOG_DIR/backend.log, $LOG_DIR/frontend.log"
  echo "Stop with: scripts/service.sh stop"
  exit 0
fi

cleanup() {
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "Starting backend  -> http://$HOST:$BACKEND_PORT/api/status"
# shellcheck disable=SC2086
python3 "$ROOT/client/backend.py" --host "$HOST" --port "$BACKEND_PORT" ${BACKEND_ARGS[@]+"${BACKEND_ARGS[@]}"} &
BACKEND_PID=$!

# Give the backend a moment so Vite proxy has something to hit.
sleep 1
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo "error: backend exited on startup. See output above." >&2
  exit 1
fi

echo "Starting frontend -> http://$HOST:$FRONTEND_PORT"
export VITE_API_PROXY="${VITE_API_PROXY:-http://$HOST:$BACKEND_PORT}"
(cd "$ROOT/client/frontend" && npm run dev -- --host "$HOST" --port "$FRONTEND_PORT" --strictPort ${VITE_ARGS[@]+"${VITE_ARGS[@]}"}) &
FRONTEND_PID=$!

# If either process dies, stop the other and exit.
wait -n "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
echo "One of the processes exited; shutting down." >&2
exit 1
