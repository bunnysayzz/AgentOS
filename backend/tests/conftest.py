"""Pytest fixtures for Firestore-backed integration tests (no Firebase needed).

Uses an in-memory fake Firestore client and a monkeypatched Firebase token
verifier, so the whole suite runs offline and deterministically.
"""

import asyncio
import hashlib
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.main import app
from tests.fake_firestore import FakeFirestoreClient


# ─── Async session scope ─────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ─── Fake Firestore ──────────────────────────────────


@pytest.fixture
def firestore_client() -> FakeFirestoreClient:
    """A fresh in-memory Firestore per test."""
    return FakeFirestoreClient()


# ─── Fake Firebase token verification ────────────────


def fake_verify_firebase_token(token: str) -> dict:
    """Stand-in for app.core.firebase.verify_firebase_token.

    Token format: ``firebase.<email>`` (or ``firebase.<email>:<name>``).
    A token whose name ends with ``~<url>`` carries a picture claim (mirrors
    the Google ``picture`` claim). Anything else raises ValueError, mirroring
    an invalid token.
    """
    if not token.startswith("firebase."):
        raise ValueError("Invalid Firebase token")
    body = token[len("firebase."):]
    # Split on the FIRST colon only — the optional name suffix may itself
    # contain colons (a Google photo URL like https://…).
    email, sep, name = body.partition(":")
    name = name if sep else email.split("@")[0]
    picture = None
    if "~" in name:
        name, picture = name.split("~", 1)
    return {
        "uid": hashlib.sha256(token.encode()).hexdigest()[:28],
        "email": email,
        "name": name,
        "picture": picture,
    }


@pytest.fixture(autouse=True)
def fake_firebase_token_auth(monkeypatch, firestore_client):
    """Wire the fake Firestore + fake token verifier into the app."""
    from app.api import deps as deps_module
    from app.api import auth as auth_module
    from app.core import firebase as firebase_core
    from app.core import database as database_module

    monkeypatch.setattr(deps_module, "verify_firebase_token", fake_verify_firebase_token)
    monkeypatch.setattr(auth_module, "verify_firebase_token", fake_verify_firebase_token)
    monkeypatch.setattr(firebase_core, "verify_firebase_token", fake_verify_firebase_token)

    def _override_get_db():
        yield FirestoreDB(client=firestore_client)

    monkeypatch.setattr(database_module, "_db", FirestoreDB(client=firestore_client))
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


# ─── Test client ──────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client with the fake Firestore wired in."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Service-level session (replaces the old SQLAlchemy db_session) ──


@pytest.fixture
async def db_session(firestore_client) -> FirestoreDB:
    """A Firestore-backed DB handle for direct service-level tests."""
    return FirestoreDB(client=firestore_client)


# ─── Test user fixtures ───────────────────────────────


@pytest_asyncio.fixture
async def test_user_data():
    """Default test user registration data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
    }


@pytest_asyncio.fixture
async def test_user(client: AsyncClient, test_user_data: dict) -> dict:
    """Create a Firebase-token user via auto-registration on first /auth/me."""
    token = f"firebase.{test_user_data['email']}:{test_user_data['full_name']}"
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    return {
        "id": data["id"],
        "email": data["email"],
        "username": data["username"],
        "full_name": data["full_name"],
        "access_token": token,
        "refresh_token": token,
    }


@pytest_asyncio.fixture
async def auth_headers(test_user: dict) -> dict:
    """Authorization headers for the test user."""
    return {"Authorization": f"Bearer {test_user['access_token']}"}


@pytest_asyncio.fixture
async def second_user(client: AsyncClient) -> dict:
    """Create and return a second user for multi-user tests."""
    token = "firebase.other@example.com:Other User"
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    return {
        "id": data["id"],
        "email": data["email"],
        "username": data["username"],
        "auth_headers": {"Authorization": f"Bearer {token}"},
    }


# ─── Test workspace fixture ───────────────────────────


@pytest_asyncio.fixture
async def test_workspace(client: AsyncClient, auth_headers: dict) -> dict:
    """Create and return a test workspace."""
    response = await client.post(
        "/api/v1/workspaces/",
        json={"name": "Test Workspace", "description": "A workspace for testing"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


# ─── Provider config fixture ──────────────────────────


@pytest_asyncio.fixture
async def openai_provider(client: AsyncClient, auth_headers: dict) -> dict:
    """Configure the OpenAI provider through the API."""
    response = await client.put(
        "/api/v1/mcp/providers/openai",
        json={
            "provider": "openai",
            "api_key": "sk-test-1234567890abcdef",
            "default_model": "gpt-4o-mini",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()


# ─── Fake HTTP transport for mocking provider connections ──


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self) -> dict:
        return self._json_data


class FakeAsyncClient:
    """Drop-in replacement for httpx.AsyncClient used in tests."""

    def __init__(self, *args, **kwargs):
        self._get_response = FakeResponse(200, {"data": [{"id": "gpt-4o"}]})
        self._post_response = FakeResponse(
            200,
            {
                "content": [{"text": "ok"}],
                "usage": {"input_tokens": 3, "output_tokens": 3},
            },
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url: str, **kwargs) -> FakeResponse:
        return self._get_response

    async def post(self, url: str, **kwargs) -> FakeResponse:
        return self._post_response


# ─── Mocked OpenAI-compatible LLM call ────────────────


async def fake_openai_compatible_call(
    api_key: str,
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int | None,
    base_url: str = "https://api.openai.com/v1",
) -> dict:
    """Canned OpenAI-format response used to mock MCP chat calls."""
    return {
        "choices": [
            {"message": {"role": "assistant", "content": "Mock LLM response"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
