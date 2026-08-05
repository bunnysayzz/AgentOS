"""Tests for the MCP fixes round:

1. Provider chat falls back to the metadata base URL (all providers usable).
2. Anthropic default model is a current, non-retired one.
3. Cost is computed for the *actual* model used on fallback.
4. Real token streaming (SSE) yields deltas + a done event and records the call.
5. Global (workspace-level) memory consolidation trims the oldest entries.

Uses the in-memory FakeFirestore; no real LLM/HTTP calls are made.
"""

import pytest

from app.core.db import FirestoreDB
from app.models.mcp import LLMProvider
from app.schemas.mcp import ChatCompletionRequest, ChatMessage, ProviderConfigCreate
from app.schemas.memory import MemoryEntryCreate
from app.services import mcp_service, memory_service, provider_service


# ─── Provider routing fixes ─────────────────────────


class TestProviderRouting:
    def test_anthropic_default_model_is_current(self):
        model = mcp_service._get_model_for_provider(LLMProvider.ANTHROPIC)
        assert model == "claude-3-5-haiku-20241022"
        # The retired model must never be used as the fallback default.
        assert "claude-3-haiku-20240307" not in model

    async def test_else_branch_uses_metadata_base_url(
        self, db_session: FirestoreDB, monkeypatch
    ):
        # Bluesminds is OpenAI-compatible but not in the explicit if-branch;
        # with no stored base_url it must fall back to the metadata URL (same
        # behaviour as test_connection).
        await provider_service.upsert_provider_config(
            db_session,
            ProviderConfigCreate(provider=LLMProvider.BLUESMINDS, api_key="sk-test-bluesminds"),
        )

        captured = {}

        async def fake_call(api_key, messages, model, temperature, max_tokens, base_url="https://api.openai.com/v1"):
            captured["base_url"] = base_url
            captured["model"] = model
            return {
                "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }

        monkeypatch.setattr(mcp_service, "_call_openai_compatible", fake_call)

        resp = await mcp_service.route_chat_completion(
            db_session,
            ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="ping")]),
        )
        assert captured["base_url"] == "https://api.bluesminds.com/v1"
        assert resp.choices[0]["message"]["content"] == "hi"

    async def test_cost_uses_actual_model_on_fallback(
        self, db_session: FirestoreDB, monkeypatch
    ):
        # OpenAI configured but failing with a rate-limit error → falls back to
        # Cerebras. Cost must be priced with Cerebras' default model, not the
        # originally requested gpt-4o-mini.
        await provider_service.upsert_provider_config(
            db_session,
            ProviderConfigCreate(provider=LLMProvider.OPENAI, api_key="sk-openai-1"),
        )
        await provider_service.upsert_provider_config(
            db_session,
            ProviderConfigCreate(
                provider=LLMProvider.CEREBRAS,
                api_key="csk-test-1",
                base_url="https://api.cerebras.ai/v1",
            ),
        )

        async def fake_call(api_key, messages, model, temperature, max_tokens, base_url="https://api.openai.com/v1"):
            if "openai.com" in base_url:
                raise RuntimeError("Rate limit exceeded: retry later")
            return {
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }

        monkeypatch.setattr(mcp_service, "_call_openai_compatible", fake_call)

        costs = {}

        def fake_cost(model_name, prompt_tokens, completion_tokens):
            costs["model"] = model_name
            return 0.42

        monkeypatch.setattr(mcp_service, "calculate_cost", fake_cost)

        resp = await mcp_service.route_chat_completion(
            db_session,
            ChatCompletionRequest(model="gpt-4o-mini", messages=[ChatMessage(role="user", content="ping")]),
        )
        assert costs["model"] == "gpt-oss-120b"  # Cerebras default model
        assert resp.cost_usd == 0.42
        assert resp.provider == LLMProvider.CEREBRAS


# ─── Streaming ──────────────────────────────────────


class TestStreaming:
    async def test_stream_yields_deltas_done_and_records(
        self, db_session: FirestoreDB, monkeypatch
    ):
        await provider_service.upsert_provider_config(
            db_session,
            ProviderConfigCreate(
                provider=LLMProvider.GROQ,
                api_key="gsk-stream-test",
                base_url="https://api.groq.com/openai/v1",
            ),
        )

        async def fake_stream(api_key, messages, model, temperature, max_tokens, base_url):
            yield {"type": "delta", "content": "Hello"}
            yield {"type": "delta", "content": " world"}
            yield {"type": "usage", "prompt_tokens": 9, "completion_tokens": 4, "total_tokens": 13}

        monkeypatch.setattr(mcp_service, "_stream_openai_compatible", fake_stream)

        events = [
            evt
            async for evt in mcp_service.stream_chat_completion(
                db_session,
                ChatCompletionRequest(
                    model="llama-3.3-70b-versatile",
                    messages=[ChatMessage(role="user", content="hi")],
                ),
            )
        ]

        deltas = [e["content"] for e in events if e["type"] == "delta"]
        assert deltas == ["Hello", " world"]

        done = [e for e in events if e["type"] == "done"]
        assert len(done) == 1
        assert done[0]["provider"] == "groq"
        assert done[0]["usage"]["total_tokens"] == 13
        assert done[0]["cost_usd"] > 0

        # The streamed call was recorded in the ledger as a streamed call.
        rows = db_session.query(mcp_service.LLM_CALLS)
        assert any(r.get("is_streaming") and not r.get("is_error") for r in rows)

    async def test_stream_emits_error_when_no_provider(self, db_session: FirestoreDB):
        events = [
            evt
            async for evt in mcp_service.stream_chat_completion(
                db_session,
                ChatCompletionRequest(model="gpt-4o", messages=[ChatMessage(role="user", content="hi")]),
            )
        ]
        assert events and events[-1]["type"] == "error"


# ─── Memory consolidation ───────────────────────────


class TestWorkspaceConsolidation:
    async def test_consolidate_workspace_trims_oldest(
        self, db_session: FirestoreDB, test_user: dict
    ):
        from app.schemas.workspace import WorkspaceCreate
        from app.services import workspace_service

        ws = await workspace_service.create_workspace(
            db_session, WorkspaceCreate(name="Mem WS"), owner=test_user
        )
        for i in range(12):
            await memory_service.create_entry(
                db_session,
                MemoryEntryCreate(role="user", content=f"entry {i}", session_id="s1"),
                workspace_id=ws["id"],
            )

        count = await memory_service.consolidate_workspace_memory(
            db_session, ws["id"], max_entries=5
        )
        assert count == 7

        remaining = await memory_service.list_workspace_memory(
            db_session, ws["id"], limit=100
        )
        assert len(remaining) == 5

    async def test_consolidate_keeps_important_entries(
        self, db_session: FirestoreDB, test_user: dict
    ):
        from app.schemas.workspace import WorkspaceCreate
        from app.services import workspace_service

        ws = await workspace_service.create_workspace(
            db_session, WorkspaceCreate(name="Mem WS 2"), owner=test_user
        )
        important = None
        for i in range(6):
            entry = await memory_service.create_entry(
                db_session,
                MemoryEntryCreate(role="user", content=f"entry {i}", session_id="s1"),
                workspace_id=ws["id"],
            )
            if i == 0:
                important = entry["id"]
                await memory_service.update_importance(db_session, important, score=9.0)

        await memory_service.consolidate_workspace_memory(db_session, ws["id"], max_entries=3)
        remaining = await memory_service.list_workspace_memory(
            db_session, ws["id"], limit=100
        )
        ids = {r["id"] for r in remaining}
        assert important in ids  # high-importance entry survives trimming
