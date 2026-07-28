#!/bin/bash

# Cowork + CoSight - Stop All Services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║     Cowork + CoSight - Stopping          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

STOPPED_SOMETHING=false

stop_pid() {
    local name=$1
    local pidfile="$PID_DIR/$2"
    local port=$3

    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}Stopping $name (PID: $pid)...${NC}"
            kill "$pid" 2>/dev/null
            for i in {1..10}; do
                ps -p "$pid" > /dev/null 2>&1 || break
                sleep 0.5
            done
            ps -p "$pid" > /dev/null 2>&1 && kill -9 "$pid" 2>/dev/null
            echo -e "${GREEN}✓ $name stopped${NC}"
            STOPPED_SOMETHING=true
        else
            echo -e "${YELLOW}$name was not running${NC}"
        fi
        rm -f "$pidfile"
    else
        echo -e "${YELLOW}No $name PID file found${NC}"
    fi

    # Also clear by port
    if [ -n "$port" ]; then
        local port_pid=$(lsof -ti:"$port" 2>/dev/null)
        if [ -n "$port_pid" ]; then
            echo -e "${YELLOW}Killing orphaned process on port $port (PID: $port_pid)${NC}"
            kill "$port_pid" 2>/dev/null
            STOPPED_SOMETHING=true
        fi
    fi
}

stop_pid "Backend"          "backend.pid"  8000
stop_pid "Cowork frontend"  "frontend.pid" 5173
stop_pid "CoSight frontend" "cosight.pid"  5174

echo ""
if $STOPPED_SOMETHING; then
    echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     All services stopped                 ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
else
    echo -e "${YELLOW}No running services found${NC}"
fi
