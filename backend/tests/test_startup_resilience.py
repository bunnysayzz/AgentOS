"""Startup-resilience tests — the Render deploy-timeout failure mode.

These cover the exact bug that made deploys time out: a dead/expired Firebase
credential (``invalid_grant: Token has been expired or revoked``) made the
startup model-seed Firestore call retry for ~14 minutes, the server never bound
its port, and Render's port scan gave up (``Port scan timeout reached, no open
ports detected`` → deploy "Timed out").

The regular unit suite could not catch this: it injects a fake Firestore and
uses ASGITransport, which never runs the real lifespan. These tests run the
REAL FastAPI lifespan (via TestClient) with Firestore forced to fail or hang,
and assert the app still comes up and serves /health.

Guarantees under test:
1. /health responds 200 even when Firestore is completely unavailable.
2. A hung startup warmup is bounded by STARTUP_WARMUP_TIMEOUT_SECONDS and does
   NOT block the server from binding its port.
3. Startup warmup errors are swallowed — boot always completes.
"""

import asyncio
import time

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core import firebase as firebase_core
from app.core.config import settings


def _quiet_warmups(monkeypatch) -> None:
    """Neutralize the network/Firestore warmups so tests are deterministic."""
    monkeypatch.setattr(main_module, "_warm_certs_sync", lambda: None)
    monkeypatch.setattr(main_module, "_reap_sync", lambda: None)


@pytest.fixture
def live_client() -> TestClient:
    """A TestClient that runs the REAL lifespan + middleware (unlike the async
    ASGITransport client used by the rest of the suite)."""
    return TestClient(main_module.app)


def test_health_ok_when_firestore_credential_dead(monkeypatch, live_client):
    """A revoked/expired refresh token must not prevent the app from booting.

    This mirrors the production failure: get_firestore_db() raises
    invalid_grant. The seed warmup logs a warning and startup completes.
    """

    def dead_credential(*args, **kwargs):
        raise RuntimeError("invalid_grant: Token has been expired or revoked")

    monkeypatch.setattr(firebase_core, "get_firestore_db", dead_credential)
    _quiet_warmups(monkeypatch)  # _seed_models_sync still runs real code path

    with live_client as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


def test_health_ok_when_firestore_raises_on_seed(monkeypatch, live_client):
    """Same as above but the failure surfaces while seeding the model registry
    (the exact startup path that hung in production)."""

    def dead_credential(*args, **kwargs):
        raise RuntimeError("invalid_grant: Token has been expired or revoked")

    monkeypatch.setattr(firebase_core, "get_firestore_db", dead_credential)
    _quiet_warmups(monkeypatch)

    with live_client as client:
        resp = client.get("/health")
        assert resp.status_code == 200


def test_hung_warmup_does_not_block_startup(monkeypatch, capsys):
    """A startup warmup that hangs (gRPC retry storm) is abandoned after the
    timeout — the server must still come up quickly and serve /health."""

    def hang_forever():
        time.sleep(5)  # simulates the 14-minute gRPC retry storm
        raise AssertionError("warmup should have been abandoned")

    monkeypatch.setattr(main_module, "_seed_models_sync", hang_forever)
    _quiet_warmups(monkeypatch)
    monkeypatch.setattr(settings, "STARTUP_WARMUP_TIMEOUT_SECONDS", 0.2)

    start = time.monotonic()
    with TestClient(main_module.app) as client:
        resp = client.get("/health")
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        # Bounded by the 0.2s warmup timeout — nowhere near the 5s hang.
        assert elapsed < 3, f"startup blocked by hung warmup: {elapsed:.2f}s"


def test_warmup_error_is_swallowed(monkeypatch, live_client):
    """A warmup that raises immediately must not crash the lifespan."""

    def boom(*args, **kwargs):
        raise RuntimeError("firestore connection refused")

    monkeypatch.setattr(firebase_core, "get_firestore_db", boom)
    _quiet_warmups(monkeypatch)

    with live_client as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


async def test_warmup_task_created_non_blocking(monkeypatch):
    """_spawn_bounded_warmup returns immediately (create_task) — it never
    blocks the caller, which is what guarantees the port can bind."""
    monkeypatch.setattr(settings, "STARTUP_WARMUP_TIMEOUT_SECONDS", 0.2)

    def slow():
        time.sleep(1)
        return "done"

    start = time.monotonic()
    task = main_module._spawn_bounded_warmup("probe", slow)
    created = time.monotonic() - start
    assert created < 0.5, "spawn blocked instead of returning a background task"
    # The bounded runner abandons the 1s sleep after the 0.2s timeout, so this
    # resolves quickly instead of waiting for the thread.
    await asyncio.wait_for(task, timeout=2)
