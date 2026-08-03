#!/bin/bash
# ─── AgentOS Studio Backend Entrypoint ──────────────────
# Data lives in Cloud Firestore (no database migrations needed).
set -e

echo "→ Starting AgentOS Studio API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
