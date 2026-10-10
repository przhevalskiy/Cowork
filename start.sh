#!/bin/bash

# Cowork + CoSight - Start All Services
# Backend: port 8000 (shared)
# Cowork frontend:  port 5173
# CoSight frontend: port 5174
#
# Run this from Terminal.app (not Cursor's agent shell) for processes that stay up.
# Example: cd /Users/alexprzhevalskiy/Desktop/Qodex && ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
COSIGHT_DIR="$SCRIPT_DIR/frontend-cosight"
PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/logs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

mkdir -p "$PID_DIR" "$LOG_DIR"

load_nvm() {
  export NVM_DIR="$HOME/.nvm"
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh"
  fi
}

# Start a long-lived process detached from this shell (survives terminal close).
# Usage: start_detached <name> <pidfile> <logfile> <command...>
start_detached() {
  local name=$1 pidfile=$2 logfile=$3
  shift 3
  : > "$logfile"
  # nohup + subshell: immune to SIGHUP when the launching terminal closes.
  # Avoid `disown` — it fails in non-interactive shells on macOS and kills the script (set -e).
  nohup "$@" >> "$logfile" 2>&1 < /dev/null &
  local pid=$!
  echo "$pid" > "$pidfile"
  echo -e "${GREEN}✓ $name started (PID: $pid)${NC}"
}

is_running() {
  local pidfile=$1
  [ -f "$pidfile" ] || return 1
  local pid
  pid=$(cat "$pidfile")
  ps -p "$pid" > /dev/null 2>&1
}

clear_stale_pid() {
  local name=$1 pidfile=$2
  if [ -f "$pidfile" ] && ! is_running "$pidfile"; then
    echo -e "${YELLOW}Clearing stale $name PID file${NC}"
    rm -f "$pidfile"
  fi
}

port_in_use() {
  lsof -ti:"$1" > /dev/null 2>&1
}

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║     Cowork + CoSight - Starting          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

clear_stale_pid "backend" "$PID_DIR/backend.pid"
clear_stale_pid "Cowork frontend" "$PID_DIR/frontend.pid"
clear_stale_pid "CoSight frontend" "$PID_DIR/cosight.pid"

if is_running "$PID_DIR/backend.pid"; then
  echo -e "${YELLOW}Backend already running (PID: $(cat "$PID_DIR/backend.pid")). Run ./stop.sh first.${NC}"
  exit 1
fi
if is_running "$PID_DIR/frontend.pid"; then
  echo -e "${YELLOW}Cowork frontend already running. Run ./stop.sh first.${NC}"
  exit 1
fi
if is_running "$PID_DIR/cosight.pid"; then
  echo -e "${YELLOW}CoSight frontend already running. Run ./stop.sh first.${NC}"
  exit 1
fi

for port in 8000 5173 5174; do
  if port_in_use "$port"; then
    echo -e "${RED}Port $port is already in use. Run ./stop.sh or free the port first.${NC}"
    exit 1
  fi
done

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo -e "${YELLOW}Warning: Backend .env file not found${NC}"
  if [ -f "$BACKEND_DIR/.env.example" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo -e "${YELLOW}Created .env from .env.example — add your API keys${NC}"
  fi
fi

if [ ! -f "$FRONTEND_DIR/.env" ] && [ -f "$FRONTEND_DIR/.env.example" ]; then
  cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"
fi

if [ ! -f "$COSIGHT_DIR/.env" ]; then
  echo "VITE_API_URL=http://localhost:8000" > "$COSIGHT_DIR/.env"
fi

# --- Backend ---
echo -e "${BLUE}Starting Backend...${NC}"
cd "$BACKEND_DIR"
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt --quiet
deactivate
start_detached "Backend" "$PID_DIR/backend.pid" "$LOG_DIR/backend.log" \
  bash -c "cd '$BACKEND_DIR' && exec '$BACKEND_DIR/venv/bin/uvicorn' app.main:app --host 0.0.0.0 --port 8000 --reload"

# --- Cowork frontend (vite directly — avoids npm wrapper exiting) ---
echo -e "${BLUE}Starting Cowork Frontend...${NC}"
cd "$FRONTEND_DIR"
load_nvm
if [ ! -d "node_modules" ]; then
  npm install --silent
fi
NODE_BIN="$(command -v node)"
start_detached "Cowork frontend" "$PID_DIR/frontend.pid" "$LOG_DIR/frontend.log" \
  bash -c "exec '$NODE_BIN' '$FRONTEND_DIR/node_modules/vite/bin/vite.js' --host 127.0.0.1 --port 5173"

# --- CoSight frontend ---
echo -e "${BLUE}Starting CoSight Frontend...${NC}"
cd "$COSIGHT_DIR"
load_nvm
if [ ! -d "node_modules" ]; then
  npm install --silent
fi
if [ ! -d "node_modules/@rollup/rollup-darwin-x64" ] && [ "$(uname -m)" = "x86_64" ]; then
  npm install @rollup/rollup-darwin-x64 --silent
fi
start_detached "CoSight frontend" "$PID_DIR/cosight.pid" "$LOG_DIR/cosight.log" \
  bash -c "exec '$NODE_BIN' '$COSIGHT_DIR/node_modules/vite/bin/vite.js' --host 127.0.0.1 --port 5174"

sleep 3
echo ""
echo -e "${BLUE}Checking services...${NC}"

BACKEND_RUNNING=false
FRONTEND_RUNNING=false
COSIGHT_RUNNING=false

if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  BACKEND_RUNNING=true
  echo -e "${GREEN}✓ Backend is running on http://localhost:8000${NC}"
else
  echo -e "${RED}✗ Backend failed to start. Check logs/backend.log${NC}"
fi

if curl -sf http://localhost:5173 > /dev/null 2>&1; then
  FRONTEND_RUNNING=true
  echo -e "${GREEN}✓ Cowork frontend is running on http://localhost:5173${NC}"
else
  echo -e "${RED}✗ Cowork frontend failed to start. Check logs/frontend.log${NC}"
fi

if curl -sf http://localhost:5174 > /dev/null 2>&1; then
  COSIGHT_RUNNING=true
  echo -e "${GREEN}✓ CoSight frontend is running on http://localhost:5174${NC}"
else
  echo -e "${RED}✗ CoSight frontend failed to start. Check logs/cosight.log${NC}"
fi

echo ""
if $BACKEND_RUNNING && $FRONTEND_RUNNING && $COSIGHT_RUNNING; then
  echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║     All services ready!                  ║${NC}"
  echo -e "${GREEN}║                                          ║${NC}"
  echo -e "${GREEN}║     Cowork:   http://localhost:5173      ║${NC}"
  echo -e "${GREEN}║     CoSight:  http://localhost:5174      ║${NC}"
  echo -e "${GREEN}║     Backend:  http://localhost:8000      ║${NC}"
  echo -e "${GREEN}║     API Docs: http://localhost:8000/docs ║${NC}"
  echo -e "${GREEN}║                                          ║${NC}"
  echo -e "${GREEN}║  Tip: run from Terminal.app to keep alive ║${NC}"
  echo -e "${GREEN}║     ./stop.sh   to stop all              ║${NC}"
  echo -e "${GREEN}║     ./status.sh to check health          ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
else
  echo -e "${RED}Some services failed to start. Check the logs directory.${NC}"
  exit 1
fi
