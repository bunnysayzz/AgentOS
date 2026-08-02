"""Provider Config integration tests: auto-detection, CRUD, encryption, connection testing."""

import pytest

import httpx

from app.services import provider_service
from app.models.mcp import LLMProvider
from tests.conftest import FakeAsyncClient


class TestProviderDetection:
    @pytest.mark.parametrize(
        "key,expected",
        [
            ("sk-proj-abc123", "openai"),
            ("sk-abc123", "openai"),
            ("sk-or-v1-xyz", "openrouter"),
            ("gsk_abc123", "groq"),
            ("csk-abc123", "cerebras"),
            ("AIzaSyAbCdEf123", "google"),
            ("hf_abcdef", "huggingface"),
            ("nvapi-abc", "nvidia_nim"),
            ("tgp_v1_abc", "together_ai"),
            ("v2Sq.abc123", "mistral"),
        ],
    )
    async def test_detect_known_prefixes(self, client, auth_headers, key, expected):
        resp = await client.get(
            "/api/v1/mcp/providers/detect", params={"api_key": key}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected"] is True
        assert data["provider"] == expected

    async def test_detect_unknown_key(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/mcp/providers/detect",
            params={"api_key": "totally-unknown-prefix"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["detected"] is False

    async def test_detect_requires_auth(self, client):
        resp = await client.get("/api/v1/mcp/providers/detect", params={"api_key": "sk-abc"})
        assert resp.status_code == 401


class TestProviderCRUD:
    async def test_list_is_empty_initially(self, client, auth_headers):
        resp = await client.get("/api/v1/mcp/providers", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_upsert_provider(self, client, auth_headers):
        resp = await client.put(
            "/api/v1/mcp/providers/openai",
            json={"provider": "openai", "api_key": "sk-123", "default_model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_configured"] is True
        assert data["default_model"] == "gpt-4o-mini"

    async def test_get_configured_provider(self, client, auth_headers, openai_provider):
        resp = await client.get("/api/v1/mcp/providers/openai", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_configured"] is True

    async def test_get_unconfigured_provider_404(self, client, auth_headers):
        resp = await client.get("/api/v1/mcp/providers/anthropic", headers=auth_headers)
        assert resp.status_code == 404

    async def test_upsert_replaces_api_key(self, client, auth_headers, openai_provider, db_session):
        resp = await client.put(
            "/api/v1/mcp/providers/openai",
            json={"provider": "openai", "api_key": "sk-new-key-999"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        config = await provider_service.get_provider_config(db_session, LLMProvider.OPENAI)
        assert provider_service.get_api_key_for_provider(config) == "sk-new-key-999"

    async def test_delete_provider(self, client, auth_headers, openai_provider):
        resp = await client.delete("/api/v1/mcp/providers/openai", headers=auth_headers)
        assert resp.status_code == 204
        listing = await client.get("/api/v1/mcp/providers", headers=auth_headers)
        assert listing.json() == []

    async def test_delete_unconfigured_provider_404(self, client, auth_headers):
        resp = await client.delete("/api/v1/mcp/providers/openai", headers=auth_headers)
        assert resp.status_code == 404


class TestProviderEncryption:
    async def test_api_key_stored_encrypted(self, client, auth_headers, openai_provider, db_session):
        config = await provider_service.get_provider_config(db_session, LLMProvider.OPENAI)
        assert config is not None
        assert config.encrypted_api_key != "sk-test-1234567890abcdef"
        assert "sk-test" not in config.encrypted_api_key
        # Round-trip decryption returns the original key
        assert provider_service.get_api_key_for_provider(config) == "sk-test-1234567890abcdef"


class TestConnectionTesting:
    async def test_test_connection_success(self, client, auth_headers, openai_provider, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
        resp = await client.post("/api/v1/mcp/providers/openai/test", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "openai"
        assert data["success"] is True

    async def test_test_connection_unconfigured_reports_failure(self, client, auth_headers):
        """The route always returns 200 with success=False for unconfigured providers."""
        resp = await client.post("/api/v1/mcp/providers/anthropic/test", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "not configured" in data["message"].lower()
