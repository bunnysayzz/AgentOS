"""Tests for budget tracking (LLM-call ledger) and hard-limit enforcement."""

from httpx import AsyncClient

from app.core.db import FirestoreDB, stamp
from app.models.mcp import LLMProvider
from app.services import mcp_service


def _record_call(db: FirestoreDB, workspace_id: str, cost: float = 0.25, tokens: int = 100) -> dict:
    """Insert an LLM call directly into the ledger (as the gateway would)."""
    call = stamp({
        "workspace_id": str(workspace_id),
        "agent_id": None,
        "execution_id": None,
        "provider": LLMProvider.OPENAI.value,
        "model_name": "gpt-4o",
        "system_prompt": None,
        "messages": [],
        "temperature": 0.7,
        "max_tokens": None,
        "response_content": "ok",
        "finish_reason": "stop",
        "prompt_tokens": tokens,
        "completion_tokens": tokens,
        "total_tokens": tokens * 2,
        "cost_usd": cost,
        "duration_ms": 100,
        "is_cached": False,
        "is_error": False,
        "error_message": None,
        "is_streaming": False,
    })
    db.add(mcp_service.LLM_CALLS, call)
    return call


async def _set_budget(client: AsyncClient, ws_id: str, auth_headers: dict, **kwargs) -> dict:
    resp = await client.patch(
        f"/api/v1/workspaces/{ws_id}/budget",
        json=kwargs,
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestBudgetTracksLedger:
    async def test_budget_reads_llm_call_ledger(
        self, client, auth_headers, test_workspace, firestore_client
    ):
        """The Budget page must reflect real recorded LLM calls (llm_calls)."""
        db = FirestoreDB(client=firestore_client)
        _record_call(db, test_workspace["id"], cost=1.25, tokens=500)

        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/budget", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["monthly"]["total_calls"] == 1
        assert data["monthly"]["total_cost_usd"] == 1.25
        assert data["monthly"]["total_tokens"] == 1000
        assert data["daily"]["total_cost_usd"] == 1.25
        assert data["monthly"]["by_model"] == {"openai/gpt-4o": {"calls": 1, "tokens": 1000, "cost_usd": 1.25}}

    async def test_exceeded_limit_raises_alert(self, client, auth_headers, test_workspace, firestore_client):
        db = FirestoreDB(client=firestore_client)
        _record_call(db, test_workspace["id"], cost=1.25)
        await _set_budget(
            client, test_workspace["id"], auth_headers,
            monthly_limit_usd=1.0, alert_threshold_pct=80,
        )

        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/budget", headers=auth_headers
        )
        data = resp.json()
        assert any(a["type"] == "monthly_exceeded" for a in data["alerts"])
        # No hard limit → warned but not blocked
        assert data["blocked"] is False

    async def test_zero_limit_blocks_any_spend(self, client, auth_headers, test_workspace, firestore_client):
        """A $0 monthly limit with hard_limit must block the very first call."""
        db = FirestoreDB(client=firestore_client)
        _record_call(db, test_workspace["id"], cost=0.01)
        await _set_budget(
            client, test_workspace["id"], auth_headers,
            monthly_limit_usd=0.0, hard_limit=True,
        )

        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/budget", headers=auth_headers
        )
        assert resp.json()["blocked"] is True


class TestHardLimitEnforcement:
    async def test_chat_blocked_when_over_hard_limit(
        self, client, auth_headers, test_workspace, firestore_client
    ):
        ws_id = test_workspace["id"]
        db = FirestoreDB(client=firestore_client)
        _record_call(db, ws_id, cost=2.0)
        await _set_budget(client, ws_id, auth_headers, monthly_limit_usd=1.0, hard_limit=True)

        chat = await client.post(
            "/api/v1/mcp/chat/completions",
            params={"workspace_id": ws_id},
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            headers=auth_headers,
        )
        assert chat.status_code == 402
        assert "budget" in chat.json()["detail"].lower()

    async def test_chat_allowed_when_over_budget_but_no_hard_limit(
        self, client, auth_headers, test_workspace, firestore_client
    ):
        ws_id = test_workspace["id"]
        db = FirestoreDB(client=firestore_client)
        _record_call(db, ws_id, cost=5.0)
        await _set_budget(client, ws_id, auth_headers, monthly_limit_usd=1.0, hard_limit=False)

        chat = await client.post(
            "/api/v1/mcp/chat/completions",
            params={"workspace_id": ws_id},
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            headers=auth_headers,
        )
        # No hard limit → the request proceeds (no providers configured, so the
        # gateway answers with its usual simulated all-providers-unavailable 200).
        assert chat.status_code == 200

    async def test_non_member_cannot_reach_budget_gated_chat(
        self, client, auth_headers, second_user, test_workspace, firestore_client
    ):
        """Chat scoped to a workspace stays access-controlled regardless of budget."""
        ws_id = test_workspace["id"]
        db = FirestoreDB(client=firestore_client)
        _record_call(db, ws_id, cost=2.0)
        await _set_budget(client, ws_id, auth_headers, monthly_limit_usd=1.0, hard_limit=True)

        # second_user is not a member → access denied before budget logic runs
        chat = await client.post(
            "/api/v1/mcp/chat/completions",
            params={"workspace_id": ws_id},
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
            headers=second_user["auth_headers"],
        )
        assert chat.status_code == 403


class TestWebhookAlerts:
    async def test_webhook_fires_once_per_threshold(
        self, client, auth_headers, test_workspace, firestore_client, monkeypatch
    ):
        """Alert webhooks deliver once per threshold crossing, not on every check."""
        ws_id = test_workspace["id"]
        db = FirestoreDB(client=firestore_client)
        _record_call(db, ws_id, cost=2.0)

        calls = []

        class FakeClient:
            def __init__(self, timeout=5):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None):
                calls.append((url, json))

        monkeypatch.setattr("httpx.AsyncClient", FakeClient)

        await _set_budget(
            client, ws_id, auth_headers,
            monthly_limit_usd=1.0, alert_webhook="https://hooks.example.com/alert",
        )

        first = await client.get(f"/api/v1/workspaces/{ws_id}/budget", headers=auth_headers)
        assert first.status_code == 200
        assert len(calls) == 1
        assert calls[0][0] == "https://hooks.example.com/alert"
        assert calls[0][1]["event"] == "budget_alert"
        assert calls[0][1]["blocked"] is False

        # Same state on the next check → no duplicate delivery
        await client.get(f"/api/v1/workspaces/{ws_id}/budget", headers=auth_headers)
        assert len(calls) == 1

    async def test_webhook_clears_when_budget_heals(
        self, client, auth_headers, test_workspace, firestore_client, monkeypatch
    ):
        """Once spend drops back under the limit, the next crossing alerts again."""
        ws_id = test_workspace["id"]
        db = FirestoreDB(client=firestore_client)
        _record_call(db, ws_id, cost=2.0)

        calls = []

        class FakeClient:
            def __init__(self, timeout=5):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None):
                calls.append((url, json))

        monkeypatch.setattr("httpx.AsyncClient", FakeClient)

        await _set_budget(
            client, ws_id, auth_headers,
            monthly_limit_usd=1.0, alert_webhook="https://hooks.example.com/alert",
        )
        await client.get(f"/api/v1/workspaces/{ws_id}/budget", headers=auth_headers)
        assert len(calls) == 1

        # Spend drops below the limit → state clears.
        await _set_budget(client, ws_id, auth_headers, monthly_limit_usd=100.0)
        await client.get(f"/api/v1/workspaces/{ws_id}/budget", headers=auth_headers)
        assert len(calls) == 1  # nothing to alert while healthy

        # Breach again → alerts once more.
        await _set_budget(client, ws_id, auth_headers, monthly_limit_usd=1.0)
        await client.get(f"/api/v1/workspaces/{ws_id}/budget", headers=auth_headers)
        assert len(calls) == 2
