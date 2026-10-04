#!/bin/bash
# Start/stop the feeder web stack:
#   frontend (static UI)  -> http://localhost:6606
#   backend  (JSON API)   -> http://localhost:6607
#
# Usage:
#   scripts/service.sh start [--times 07:00,18:00] [backend args...]
#   scripts/service.sh stop
#   scripts/service.sh status
#   scripts/service.sh restart
#
# Env overrides: FRONTEND_PORT, BACKEND_PORT, HOST
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_PORT="${FRONTEND_PORT:-6606}"
BACKEND_PORT="${BACKEND_PORT:-6607}"
HOST="${HOST:-127.0.0.1}"
PID_DIR="$ROOT/.pids"
LOG_DIR="$ROOT/.logs"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"

alive() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

cmd_start() {
  mkdir -p "$PID_DIR" "$LOG_DIR"
  if alive "$BACKEND_PID" || alive "$FRONTEND_PID"; then
    echo "Already running. Use '$0 stop' first."
    return 1
  fi
  # "$@" are extra args forwarded to backend.py (e.g. --times 07:00,18:00)
  # shellcheck disable=SC2086
  nohup python3 "$ROOT/client/backend.py" --host "$HOST" --port "$BACKEND_PORT" "$@" \
    >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$BACKEND_PID"
  nohup python3 -m http.server "$FRONTEND_PORT" --bind "$HOST" \
    --directory "$ROOT/client/frontend" >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$FRONTEND_PID"
  sleep 1
  echo "Frontend: http://$HOST:$FRONTEND_PORT"
  echo "Backend:  http://$HOST:$BACKEND_PORT/api/status"
}

cmd_stop() {
  local rc=0
  for pidfile in "$BACKEND_PID" "$FRONTEND_PID"; do
    if alive "$pidfile"; then
      kill "$(cat "$pidfile")" && echo "Stopped $(basename "$pidfile" .pid)."
      rm -f "$pidfile"
    else
      rm -f "$pidfile"
    fi
  done
  return $rc
}

cmd_status() {
  local rc=0
  alive "$BACKEND_PID" && echo "backend:  running (pid $(cat "$BACKEND_PID"))" \
    || { echo "backend:  stopped"; rc=1; }
  alive "$FRONTEND_PID" && echo "frontend: running (pid $(cat "$FRONTEND_PID"))" \
    || { echo "frontend: stopped"; rc=1; }
  curl -s -m 5 "http://$HOST:$BACKEND_PORT/api/status" 2>/dev/null && echo || rc=1
  return $rc
}

case "${1:-status}" in
  start) shift; cmd_start "$@" ;;
  stop) cmd_stop ;;
  restart) cmd_stop; sleep 1; cmd_start ;;
  status) cmd_status ;;
  *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
