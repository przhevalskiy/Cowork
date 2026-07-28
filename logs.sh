#!/bin/bash

# Cowork - Tail Logs
# Streams backend and frontend logs side by side in real time

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║     Cowork + CoSight - Live Logs         ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"
echo -e "  ${GREEN}[BACKEND] ${NC} backend log output"
echo -e "  ${CYAN}[COWORK]  ${NC} Cowork frontend log"
echo -e "  ${YELLOW}[COSIGHT] ${NC} CoSight frontend log"
echo ""
echo -e "Press Ctrl+C to stop tailing"
echo "────────────────────────────────────────"
echo ""

if [ ! -f "$LOG_DIR/backend.log" ] && [ ! -f "$LOG_DIR/frontend.log" ] && [ ! -f "$LOG_DIR/cosight.log" ]; then
    echo -e "${RED}No log files found. Run ./start.sh first.${NC}"
    exit 1
fi

# Build file list of logs that exist
LOG_FILES=()
[ -f "$LOG_DIR/backend.log"  ] && LOG_FILES+=("$LOG_DIR/backend.log")
[ -f "$LOG_DIR/frontend.log" ] && LOG_FILES+=("$LOG_DIR/frontend.log")
[ -f "$LOG_DIR/cosight.log"  ] && LOG_FILES+=("$LOG_DIR/cosight.log")

tail -f "${LOG_FILES[@]}" 2>/dev/null | awk '
    /==> .*backend.log <=/  { source="BACKEND";  next }
    /==> .*frontend.log <=/ { source="COWORK";   next }
    /==> .*cosight.log <=/  { source="COSIGHT";  next }
    source == "BACKEND"  { print "\033[0;32m[BACKEND] \033[0m" $0 }
    source == "COWORK"   { print "\033[0;36m[COWORK]  \033[0m" $0 }
    source == "COSIGHT"  { print "\033[1;33m[COSIGHT] \033[0m" $0 }
'
