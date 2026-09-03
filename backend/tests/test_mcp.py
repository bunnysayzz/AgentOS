"""MCP Gateway integration tests: models, chat completions (mocked), fallback, cost tracking."""

from app.services import mcp_service


class TestModelRegistry:
    async def test_models_list_has_defaults(self, client, auth_headers):
        resp = await client.get("/api/v1/mcp/models", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        models = [m["model_name"] for m in data["models"]]
        assert "gpt-4o" in models or "gpt-4o-mini" in models

    async def test_seed_models_is_idempotent(self, client, auth_headers):
        r1 = await client.post("/api/v1/mcp/models/seed", headers=auth_headers)
        assert r1.status_code == 200
        assert r1.json()["seeded"] > 0

        r2 = await client.post("/api/v1/mcp/models/seed", headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["seeded"] == 0  # already seeded


class TestChatCompletions:
    async def test_chat_with_configured_provider(self, client, auth_headers, openai_provider, monkeypatch):
        async def _fake(api_key, messages, model, temperature, max_tokens, base_url="https://api.openai.com/v1"):
            return {
                "choices": [{"message": {"role": "assistant", "content": "Mock LLM response"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }

        monkeypatch.setattr(mcp_service, "_call_openai_compatible", _fake)

        resp = await client.post(
            "/api/v1/mcp/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "Mock LLM response"
        assert data["provider"] == "openai"
        assert data["usage"]["total_tokens"] == 15
        assert data["cost_usd"] >= 0

    async def test_chat_without_providers_returns_graceful_error(self, client, auth_headers):
        """No providers configured: the gateway returns a simulated failure message."""
        resp = await client.post(
            "/api/v1/mcp/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        content = resp.json()["choices"][0]["message"]["content"]
        assert "unavailable" in content.lower() or "No configured providers" in content

    async def test_fallback_to_next_provider_on_rate_limit(
        self, client, auth_headers, openai_provider, monkeypatch
    ):
        # Configure a second provider (deepseek)
        await client.put(
            "/api/v1/mcp/providers/deepseek",
            json={"provider": "deepseek", "api_key": "ds-key-1", "default_model": "deepseek-chat"},
            headers=auth_headers,
        )

        async def _flaky(api_key, messages, model, temperature, max_tokens, base_url="https://api.openai.com/v1"):
            if model == "deepseek-chat":
                # Fallback provider succeeds
                return {
                    "choices": [{"message": {"role": "assistant", "content": "Fallback response"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
                }
            raise mcp_service.MCPError("Rate limit exceeded for model", 429)

        monkeypatch.setattr(mcp_service, "_call_openai_compatible", _flaky)

        resp = await client.post(
            "/api/v1/mcp/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "deepseek"
        assert data["choices"][0]["message"]["content"] == "Fallback response"

    async def test_all_providers_fail_returns_error(self, client, auth_headers, openai_provider, monkeypatch):
        async def _always_fail(api_key, messages, model, temperature, max_tokens, base_url="https://api.openai.com/v1"):
            raise mcp_service.MCPError("authentication failed", 401)

        monkeypatch.setattr(mcp_service, "_call_openai_compatible", _always_fail)

        resp = await client.post(
            "/api/v1/mcp/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        content = resp.json()["choices"][0]["message"]["content"]
        assert "unavailable" in content.lower()

    async def test_chat_requires_valid_role(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/mcp/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "superhero", "content": "Hi"}]},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestCostTracking:
    async def test_cost_dashboard_reflects_calls(self, client, auth_headers, openai_provider, monkeypatch):
        async def _fake(api_key, messages, model, temperature, max_tokens, base_url="https://api.openai.com/v1"):
            return {
                "choices": [{"message": {"role": "assistant", "content": "x"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
            }

        monkeypatch.setattr(mcp_service, "_call_openai_compatible", _fake)
        await client.post(
            "/api/v1/mcp/chat/completions",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_headers,
        )

        costs = await client.get("/api/v1/mcp/costs", headers=auth_headers)
        assert costs.status_code == 200
        data = costs.json()
        assert data["summary"]["total_calls"] == 1
        assert data["summary"]["total_tokens"] == 1500
        assert data["summary"]["total_cost_usd"] > 0

        calls = await client.get("/api/v1/mcp/calls", headers=auth_headers)
        assert calls.status_code == 200
        call_list = calls.json()
        assert len(call_list) == 1
        assert call_list[0]["model_name"] == "gpt-4o-mini"
