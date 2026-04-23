#!/bin/bash
# =============================================================================
# Ospra OS — unified run script
# =============================================================================
#
# Consolidates: start-local.sh, start_backend.sh, start_dev_server.sh,
#               START_CLEAN.sh, START_SERVERS.sh, STOP_SERVERS.sh,
#               RESTART_BACKEND.sh, RESTART_BACKEND_WITH_ENV.sh,
#               RESTART_FRONTEND.sh
#
# Usage:
#   ./scripts/run.sh start            # start backend + frontend
#   ./scripts/run.sh backend          # start backend only
#   ./scripts/run.sh frontend         # start frontend only
#   ./scripts/run.sh stop             # kill backend + frontend
#   ./scripts/run.sh restart          # stop + start
#   ./scripts/run.sh restart-backend  # restart backend only (runs healthcheck)
#   ./scripts/run.sh restart-frontend # restart frontend only
#   ./scripts/run.sh status           # show what's running on each port
#   ./scripts/run.sh logs             # tail backend + frontend logs
#   ./scripts/run.sh clean            # stop + clear __pycache__ + restart
#
# Ports:
#   8001 — OspraOS backend (matches Render production)
#   5173 — frontend dev server
#
# =============================================================================

set -e

# Resolve project root regardless of where this script is invoked from
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKEND_PORT=8001
FRONTEND_PORT=5173
LOGS_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOGS_DIR"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

_check_env() {
  if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "[ERROR] .env file missing at $PROJECT_ROOT/.env"
    echo "        Copy .env.local to .env and configure it."
    exit 1
  fi
}

_port_in_use() {
  lsof -ti:"$1" >/dev/null 2>&1
}

_kill_port() {
  local port=$1
  local label=$2
  if _port_in_use "$port"; then
    echo "  • Stopping $label on port $port..."
    lsof -ti:"$port" | xargs kill -9 2>/dev/null || true
    sleep 1
    echo "    stopped."
  else
    echo "  • $label (port $port) — already stopped."
  fi
}

_start_backend() {
  _check_env
  if _port_in_use "$BACKEND_PORT"; then
    echo "[WARN] Port $BACKEND_PORT already in use. Run './scripts/run.sh stop' first."
    return 1
  fi
  echo "[BACKEND] Starting OspraOS on port $BACKEND_PORT..."
  # Load .env (but not DATABASE_URL — let the app decide local vs. prod)
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
  nohup uv run uvicorn ospra_os.main:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" --reload \
    > "$LOGS_DIR/backend.log" 2>&1 &
  sleep 3
  if _port_in_use "$BACKEND_PORT"; then
    echo "[BACKEND] Running at http://localhost:$BACKEND_PORT"
    echo "[BACKEND] API docs: http://localhost:$BACKEND_PORT/docs"
  else
    echo "[BACKEND] FAILED to start — check $LOGS_DIR/backend.log"
    tail -20 "$LOGS_DIR/backend.log"
    return 1
  fi
}

_start_frontend() {
  if _port_in_use "$FRONTEND_PORT"; then
    echo "[WARN] Port $FRONTEND_PORT already in use. Run './scripts/run.sh stop' first."
    return 1
  fi
  echo "[FRONTEND] Starting on port $FRONTEND_PORT..."
  (
    cd "$PROJECT_ROOT/frontend"
    nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
  )
  sleep 4
  if _port_in_use "$FRONTEND_PORT"; then
    echo "[FRONTEND] Running at http://localhost:$FRONTEND_PORT"
  else
    echo "[FRONTEND] FAILED to start — check $LOGS_DIR/frontend.log"
    tail -20 "$LOGS_DIR/frontend.log"
    return 1
  fi
}

_healthcheck() {
  echo "[HEALTH] Checking backend..."
  curl -s "http://localhost:$BACKEND_PORT/api/dashboard/v2/health" \
    | python3 -m json.tool 2>&1 | head -20 || echo "  (no response)"
}

# -----------------------------------------------------------------------------
# Subcommands
# -----------------------------------------------------------------------------

case "${1:-}" in
  start)
    echo "===================="
    echo "  Ospra OS — START"
    echo "===================="
    _start_backend
    _start_frontend
    echo ""
    echo "✓ All services up. Use './scripts/run.sh stop' when done."
    ;;

  backend)
    _start_backend
    ;;

  frontend)
    _start_frontend
    ;;

  stop)
    echo "===================="
    echo "  Ospra OS — STOP"
    echo "===================="
    _kill_port "$BACKEND_PORT" "Backend"
    _kill_port "$FRONTEND_PORT" "Frontend"
    # Extra safety: kill any stragglers by process name
    pkill -f "uvicorn ospra_os" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    echo ""
    echo "✓ All services stopped."
    ;;

  restart)
    "$0" stop
    echo ""
    "$0" start
    ;;

  restart-backend)
    _kill_port "$BACKEND_PORT" "Backend"
    pkill -f "uvicorn ospra_os" 2>/dev/null || true
    sleep 2
    _start_backend
    echo ""
    _healthcheck
    ;;

  restart-frontend)
    _kill_port "$FRONTEND_PORT" "Frontend"
    pkill -f "vite" 2>/dev/null || true
    sleep 2
    _start_frontend
    ;;

  status)
    echo "===================="
    echo "  Ospra OS — STATUS"
    echo "===================="
    if _port_in_use "$BACKEND_PORT"; then
      echo "  ✓ Backend: http://localhost:$BACKEND_PORT (running)"
    else
      echo "  ✗ Backend: not running"
    fi
    if _port_in_use "$FRONTEND_PORT"; then
      echo "  ✓ Frontend: http://localhost:$FRONTEND_PORT (running)"
    else
      echo "  ✗ Frontend: not running"
    fi
    ;;

  logs)
    echo "Tailing logs (Ctrl+C to exit)..."
    tail -f "$LOGS_DIR/backend.log" "$LOGS_DIR/frontend.log"
    ;;

  clean)
    "$0" stop
    echo ""
    echo "Clearing Python caches..."
    find "$PROJECT_ROOT" -path "$PROJECT_ROOT/.venv" -prune -o \
      -type d -name "__pycache__" -print -exec rm -rf {} + 2>/dev/null || true
    echo ""
    "$0" start
    ;;

  *)
    cat <<EOF
Usage: $0 <command>

Commands:
  start              Start backend + frontend
  backend            Start backend only
  frontend           Start frontend only
  stop               Stop backend + frontend
  restart            Stop everything, then start everything
  restart-backend    Restart backend + run healthcheck
  restart-frontend   Restart frontend only
  status             Show what's running
  logs               Tail backend + frontend logs
  clean              Stop, clear __pycache__, start

Ports:
  8001  OspraOS backend (matches Render)
  5173  Frontend dev server
EOF
    exit 1
    ;;
esac
