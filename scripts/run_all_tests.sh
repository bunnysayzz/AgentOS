#!/usr/bin/env bash
#
# run_all_tests.sh — run the ENTIRE AgentOS Studio test pipeline:
#   1. Backend  : pytest (unit + API + service tests)
#   2. Frontend : tsc typecheck, eslint, vitest (unit/component)
#   3. E2E      : Playwright smoke tests (boots real backend + frontend)
#
# This is the single entrypoint for "test it".
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0

run() {
  local name="$1"
  shift
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  if "$@" > /tmp/agentos-test-suite.log 2>&1; then
    echo "  ✅ $name — PASSED"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $name — FAILED"
    tail -40 /tmp/agentos-test-suite.log
    FAIL=$((FAIL + 1))
  fi
}

echo "AgentOS Studio — Full test pipeline"
echo "===================================="

# ── Backend ─────────────────────────────────────────────────────────────
if [ ! -x backend/.venv/bin/python ]; then
  echo ">> Creating backend virtualenv..."
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install --quiet --upgrade pip
fi
if ! backend/.venv/bin/python -c 'import fastapi, pytest, sqlalchemy' 2>/dev/null; then
  echo ">> Installing backend dependencies..."
  backend/.venv/bin/pip install --quiet -r backend/requirements.txt
fi

run "Backend tests (pytest)" bash -c 'cd backend && .venv/bin/python -m pytest -q'

# ── Frontend ────────────────────────────────────────────────────────────
if [ ! -d frontend/node_modules ]; then
  echo ">> Installing frontend dependencies..."
  (cd frontend && npm install --silent)
fi

run "Frontend typecheck (tsc)" bash -c 'cd frontend && npx tsc --noEmit'
run "Frontend lint (eslint)"   bash -c 'cd frontend && npm run lint'
run "Frontend unit tests (vitest)" bash -c 'cd frontend && npx vitest run'

# ── E2E ─────────────────────────────────────────────────────────────────
PLAYWRIGHT_CACHE=""
if [ -d "$HOME/Library/Caches/ms-playwright" ]; then
  PLAYWRIGHT_CACHE="$HOME/Library/Caches/ms-playwright"
elif [ -d "$HOME/.cache/ms-playwright" ]; then
  PLAYWRIGHT_CACHE="$HOME/.cache/ms-playwright"
fi
if [ -z "$PLAYWRIGHT_CACHE" ] || ! ls "$PLAYWRIGHT_CACHE" 2>/dev/null | grep -q chromium; then
  echo ">> Installing Playwright Chromium..."
  (cd frontend && npx playwright install chromium >/dev/null 2>&1 || npx playwright install chromium)
fi

run "End-to-end tests (playwright)" bash -c 'cd frontend && npx playwright test'

# ── Summary ─────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════"
if [ "$FAIL" -gt 0 ]; then
  echo "  RESULT: $PASS suite(s) passed, $FAIL suite(s) FAILED"
  exit 1
fi
echo "  RESULT: ALL $PASS SUITES PASSED 🎉"
echo "════════════════════════════════════════════════"
