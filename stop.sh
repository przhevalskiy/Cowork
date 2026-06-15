#!/bin/bash

# Cowork - Stop All Services
# This script stops the backend and frontend services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/.pids"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║         Cowork - Stopping Services    ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

STOPPED_SOMETHING=false

# Stop Backend
if [ -f "$PID_DIR/backend.pid" ]; then
    BACKEND_PID=$(cat "$PID_DIR/backend.pid")
    if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
        echo -e "${BLUE}Stopping Backend (PID: $BACKEND_PID)...${NC}"
        kill "$BACKEND_PID" 2>/dev/null

        # Wait for process to stop
        for i in {1..10}; do
            if ! ps -p "$BACKEND_PID" > /dev/null 2>&1; then
                break
            fi
            sleep 0.5
        done

        # Force kill if still running
        if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing backend...${NC}"
            kill -9 "$BACKEND_PID" 2>/dev/null
        fi

        echo -e "${GREEN}✓ Backend stopped${NC}"
        STOPPED_SOMETHING=true
    else
        echo -e "${YELLOW}Backend was not running${NC}"
    fi
    rm -f "$PID_DIR/backend.pid"
else
    echo -e "${YELLOW}No backend PID file found${NC}"
fi

# Stop Frontend
if [ -f "$PID_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat "$PID_DIR/frontend.pid")
    if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
        echo -e "${BLUE}Stopping Frontend (PID: $FRONTEND_PID)...${NC}"
        kill "$FRONTEND_PID" 2>/dev/null

        # Wait for process to stop
        for i in {1..10}; do
            if ! ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
                break
            fi
            sleep 0.5
        done

        # Force kill if still running
        if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
            echo -e "${YELLOW}Force killing frontend...${NC}"
            kill -9 "$FRONTEND_PID" 2>/dev/null
        fi

        echo -e "${GREEN}✓ Frontend stopped${NC}"
        STOPPED_SOMETHING=true
    else
        echo -e "${YELLOW}Frontend was not running${NC}"
    fi
    rm -f "$PID_DIR/frontend.pid"
else
    echo -e "${YELLOW}No frontend PID file found${NC}"
fi

# Also kill any orphaned processes on the ports
echo -e "${BLUE}Checking for orphaned processes...${NC}"

# Kill any process on port 8000 (backend)
BACKEND_PORT_PID=$(lsof -ti:8000 2>/dev/null)
if [ -n "$BACKEND_PORT_PID" ]; then
    echo -e "${YELLOW}Killing orphaned process on port 8000 (PID: $BACKEND_PORT_PID)${NC}"
    kill "$BACKEND_PORT_PID" 2>/dev/null
    STOPPED_SOMETHING=true
fi

# Kill any process on port 5173 (frontend)
FRONTEND_PORT_PID=$(lsof -ti:5173 2>/dev/null)
if [ -n "$FRONTEND_PORT_PID" ]; then
    echo -e "${YELLOW}Killing orphaned process on port 5173 (PID: $FRONTEND_PORT_PID)${NC}"
    kill "$FRONTEND_PORT_PID" 2>/dev/null
    STOPPED_SOMETHING=true
fi

echo ""
if $STOPPED_SOMETHING; then
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     All Cowork services stopped       ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
else
    echo -e "${YELLOW}No running services found${NC}"
fi
