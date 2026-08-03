#!/usr/bin/env bash
set -e

# ─── AgentOS Studio — Start Script ─────────────────────────────────────────
# Kills existing processes, starts backend + frontend, opens browser.
# Press Ctrl+C to stop both servers.
# ────────────────────────────────────────────────────────────────────────────

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="/tmp/agentos-venv"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Track child PIDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""

# ─── Cleanup handler ─────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}⏹  Shutting down...${NC}"

    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "  ${BLUE}Stopping backend (PID $BACKEND_PID)...${NC}"
        kill "$BACKEND_PID" 2>/dev/null
        wait "$BACKEND_PID" 2>/dev/null || true
    fi

    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "  ${BLUE}Stopping frontend (PID $FRONTEND_PID)...${NC}"
        kill "$FRONTEND_PID" 2>/dev/null
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi

    # Also kill any lingering uvicorn/node processes from this session
    lsof -t -i:8000 | xargs kill 2>/dev/null || true
    lsof -t -i:5173 | xargs kill 2>/dev/null || true

    echo -e "${GREEN}✅ All stopped.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ─── Kill existing processes on our ports ───────────────────────────────
echo -e "${BLUE}🔍 Checking for existing processes...${NC}"
BACKPORT_PID=$(lsof -t -i:8000 2>/dev/null || true)
FEPORT_PID=$(lsof -t -i:5173 2>/dev/null || true)

if [ -n "$BACKPORT_PID" ]; then
    echo -e "  ${YELLOW}Killing backend on port 8000 (PID $BACKPORT_PID)...${NC}"
    kill "$BACKPORT_PID" 2>/dev/null || true
    sleep 1
fi

if [ -n "$FEPORT_PID" ]; then
    echo -e "  ${YELLOW}Killing frontend on port 5173 (PID $FEPORT_PID)...${NC}"
    kill "$FEPORT_PID" 2>/dev/null || true
    sleep 1
fi

# ─── Start Backend ───────────────────────────────────────────────────────
echo -e "\n${BLUE}🚀 Starting backend...${NC}"

cd "$BACKEND_DIR"

# Activate virtualenv
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo -e "  ${YELLOW}Creating virtualenv at $VENV_DIR...${NC}"
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

if ! command -v uvicorn &> /dev/null || ! command -v alembic &> /dev/null; then
    echo -e "  ${YELLOW}Installing backend dependencies...${NC}"
    pip install -e .
fi

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name '*.pyc' -delete 2>/dev/null || true

# Run migrations against the configured database (see backend/.env)
echo -e "  ${GREEN}Running migrations...${NC}"
alembic upgrade head 2>&1 | tail -3

# Start backend
echo -e "  ${GREEN}Starting uvicorn on port 8000...${NC}"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo -e "  ${GREEN}Backend PID: $BACKEND_PID${NC}"

# Wait for backend to be ready
echo -e "  ${YELLOW}Waiting for backend to be ready...${NC}"
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Backend ready!${NC}"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo -e "  ${RED}❌ Backend failed to start${NC}"
        cleanup
        exit 1
    fi
    sleep 1
done

# ─── Start Frontend ──────────────────────────────────────────────────────
echo -e "\n${BLUE}🎨 Starting frontend...${NC}"

cd "$FRONTEND_DIR"

# Install deps if needed
if [ ! -d "node_modules" ]; then
    echo -e "  ${YELLOW}Installing dependencies...${NC}"
    npm install --silent 2>&1 | tail -3
fi

# Start frontend
echo -e "  ${GREEN}Starting Vite on port 5173...${NC}"
npx vite --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!
echo -e "  ${GREEN}Frontend PID: $FRONTEND_PID${NC}"

# Wait for frontend to be ready
echo -e "  ${YELLOW}Waiting for frontend to be ready...${NC}"
for i in $(seq 1 15); do
    if curl -s -o /dev/null http://localhost:5173/ 2>/dev/null; then
        echo -e "  ${GREEN}✅ Frontend ready!${NC}"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo -e "  ${RED}❌ Frontend failed to start${NC}"
        cleanup
        exit 1
    fi
    sleep 1
done

# ─── Done ─────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ AgentOS Studio is running!${NC}"
echo -e "${GREEN}  📍 Frontend:  http://localhost:5173${NC}"
echo -e "${GREEN}  📍 Backend:   http://localhost:8000${NC}"
echo -e "${GREEN}  📍 Health:    http://localhost:8000/health${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop both servers.${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

# Open browser
echo -e "\n${BLUE}🌐 Opening browser...${NC}"
if command -v open &> /dev/null; then
    open http://localhost:5173
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173
fi

# Wait for Ctrl+C
wait $BACKEND_PID $FRONTEND_PID
