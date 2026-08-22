#!/usr/bin/env python3
"""Read-only live smoke test against the real AgentOS backend + Firebase.

Boots the FastAPI app in-process with backend/.env (real Firebase creds)
and probes safe, read-only endpoints. Never writes data, so it is safe to
run against a production deployment's configuration.

Usage:
    cd backend && python ../scripts/smoke_live.py

Exit codes:
    0  all checks passed
    1  a check failed
    2  skipped (no Firebase credentials configured)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings  # noqa: E402

# Read-only endpoints. Each entry: (label, method, path, ok_statuses)
CHECKS = [
    ("health", "GET", "/health", {200}),
    ("agent templates", "GET", "/api/v1/templates", {200}),
    ("mcp marketplace", "GET", "/api/v1/mcp/marketplace", {200}),
    ("mcp model registry", "GET", "/api/v1/mcp/models", {200}),
    ("community gallery", "GET", "/api/v1/gallery/", {200}),
]


def main() -> int:
    settings = Settings()
    if not (
        settings.FIREBASE_SERVICE_ACCOUNT_JSON
        or settings.FIREBASE_PRIVATE_KEY
        or settings.FIREBASE_ACCESS_TOKEN
    ):
        print("SKIP: no Firebase credentials in backend/.env — nothing to smoke test.")
        return 2

    client = TestClient(app_factory())
    failed = 0
    for label, method, path, ok in CHECKS:
        try:
            resp = client.request(method, path)
            passed = resp.status_code in ok
            print(f"{'PASS' if passed else 'FAIL'}  {method} {path}  -> {resp.status_code}")
            if not passed:
                failed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {method} {path}  -> {type(exc).__name__}: {exc}")
            failed += 1

    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


def app_factory():
    # Imported lazily so the SKIP path above never touches Firebase init.
    from app.main import app

    return app


if __name__ == "__main__":
    raise SystemExit(main())
