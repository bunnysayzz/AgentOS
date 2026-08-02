"""Pytest fixtures for async integration tests."""

import asyncio
from typing import AsyncGenerator, Generator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app


# ─── Async session scope ─────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ─── Test database ────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session per test."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )()

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


# ─── Test client ──────────────────────────────────────


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client with overridden DB dependency."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Test user fixtures ───────────────────────────────


@pytest_asyncio.fixture
async def test_user_data():
    """Default test user registration data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "password": "testpass123",
    }


@pytest_asyncio.fixture
async def test_user(client: AsyncClient, test_user_data: dict) -> dict:
    """Register and return a test user with auth tokens."""
    # Register first
    reg_resp = await client.post("/api/v1/auth/register", json=test_user_data)
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()

    # Login to get tokens (register doesn't return them)
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": test_user_data["email"],
        "password": test_user_data["password"],
    })
    assert login_resp.status_code == 200
    token_data = login_resp.json()

    return {
        "id": user_data["id"],
        "email": user_data["email"],
        "username": user_data["username"],
        "full_name": user_data["full_name"],
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
    }


@pytest_asyncio.fixture
async def auth_headers(test_user: dict) -> dict:
    """Authorization headers for the test user."""
    return {"Authorization": f"Bearer {test_user['access_token']}"}


@pytest_asyncio.fixture
async def second_user(client: AsyncClient) -> dict:
    """Register and login a second user for multi-user tests."""
    user_data = {
        "email": "other@example.com",
        "username": "otheruser",
        "full_name": "Other User",
        "password": "testpass123",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=user_data)
    assert reg_resp.status_code == 201
    data = reg_resp.json()

    # Login to get tokens
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"],
    })
    assert login_resp.status_code == 200
    token_data = login_resp.json()

    return {
        "id": data["id"],
        "email": data["email"],
        "username": data["username"],
        "auth_headers": {"Authorization": f"Bearer {token_data['access_token']}"},
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
