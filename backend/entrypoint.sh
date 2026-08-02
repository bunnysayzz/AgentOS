#!/bin/bash
# ─── AgentOS Studio Backend Entrypoint ──────────────────
# Runs database migrations, then starts the FastAPI server.
set -e

echo "→ Running database migrations..."
alembic upgrade head
echo "→ Migrations complete."

echo "→ Starting AgentOS Studio API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
