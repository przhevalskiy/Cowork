#!/bin/bash

# Cowork - Service Status Check
# Shows running state of backend and frontend, and pings the health endpoint

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║     Cowork + CoSight - Status            ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

ALL_OK=true

check_process() {
    local name=$1
    local pidfile="$PID_DIR/$2"
    local url=$3

    echo -e "${BLUE}$name${NC}"
    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "  Process   ${GREEN}✓ Running${NC} (PID: $pid)"
        else
            echo -e "  Process   ${RED}✗ Not running${NC} (stale PID)"
            ALL_OK=false
        fi
    else
        echo -e "  Process   ${RED}✗ Not running${NC}"
        ALL_OK=false
    fi

    local status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url" 2>/dev/null)
    if [ "$status" = "200" ]; then
        echo -e "  Reachable ${GREEN}✓ $url → 200 OK${NC}"
    else
        echo -e "  Reachable ${RED}✗ $url → unreachable${NC}"
        ALL_OK=false
    fi
    echo ""
}

# Backend with provider details
echo -e "${BLUE}Backend${NC}"
if [ -f "$PID_DIR/backend.pid" ]; then
    PID=$(cat "$PID_DIR/backend.pid")
    ps -p "$PID" > /dev/null 2>&1 \
        && echo -e "  Process   ${GREEN}✓ Running${NC} (PID: $PID)" \
        || { echo -e "  Process   ${RED}✗ Not running${NC}"; ALL_OK=false; }
else
    echo -e "  Process   ${RED}✗ Not running${NC}"; ALL_OK=false
fi

HEALTH=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8000/health 2>/dev/null)
if [ "$HEALTH" = "200" ]; then
    echo -e "  Health    ${GREEN}✓ http://localhost:8000/health → 200 OK${NC}"
    HEALTH_JSON=$(curl -s --max-time 3 http://localhost:8000/health 2>/dev/null)
    if command -v python3 &>/dev/null && [ -n "$HEALTH_JSON" ]; then
        echo "$HEALTH_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for k,v in d.get('providers',{}).items():
        print(f'  Provider  {chr(10003) if v else chr(10007)} {k}')
except: pass
" 2>/dev/null
    fi
else
    echo -e "  Health    ${RED}✗ unreachable${NC}"; ALL_OK=false
fi
echo ""

check_process "Cowork Frontend"  "frontend.pid" "http://localhost:5173"
check_process "CoSight Frontend" "cosight.pid"  "http://localhost:5174"

echo "────────────────────────────────────────"
if $ALL_OK; then
    echo -e "${GREEN}✓ All systems operational${NC}"
    echo ""
    echo -e "  Cowork:   ${BLUE}http://localhost:5173${NC}"
    echo -e "  CoSight:  ${BLUE}http://localhost:5174${NC}"
    echo -e "  API Docs: ${BLUE}http://localhost:8000/docs${NC}"
else
    echo -e "${RED}✗ Some services are down — run ./start.sh to restart${NC}"
fi
echo ""
