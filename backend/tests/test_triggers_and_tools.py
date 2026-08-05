"""Tests for the new capabilities round:

1. Autonomous tool use — agents run a function-calling loop and execute tools.
2. Webhook triggers — token generation + unauthenticated inbound firing.
3. Cron scheduler — field parsing, matching, and the per-minute tick.
4. API-key verification (used by the MCP auth middleware).
5. MCP protocol server tools.
"""

from datetime import datetime

import pytest

from app.core import scheduler as sched
from app.core.db import FirestoreDB
from app.models.agent import AgentStatus, ExecutionStatus
from app.models.tool import ToolAuthType, ToolType
from app.models.workflow import WorkflowStatus
from app.schemas.agent import AgentCreate
from app.schemas.tool import ToolCreate
from app.schemas.workflow import WorkflowCreate
from app.services import agent_service, tool_service, workflow_service


# ─── Cron matcher ────────────────────────────────────


class TestCronMatcher:
    def test_star_matches_any_minute(self):
        assert sched.cron_matches("* * * * *", datetime(2026, 8, 5, 10, 30))

    def test_specific_minute_hour(self):
        assert sched.cron_matches("30 10 * * *", datetime(2026, 8, 5, 10, 30))
        assert not sched.cron_matches("30 10 * * *", datetime(2026, 8, 5, 10, 31))
        assert not sched.cron_matches("30 10 * * *", datetime(2026, 8, 5, 11, 30))

    def test_step_and_range(self):
        assert sched.cron_matches("*/15 * * * *", datetime(2026, 8, 5, 10, 30))
        assert not sched.cron_matches("*/15 * * * *", datetime(2026, 8, 5, 10, 31))
        assert sched.cron_matches("0 9-17 * * *", datetime(2026, 8, 5, 12, 0))
        assert not sched.cron_matches("0 9-17 * * *", datetime(2026, 8, 5, 8, 0))

    def test_list_field(self):
        assert sched.cron_matches("0,30 * * * *", datetime(2026, 8, 5, 10, 30))
        assert not sched.cron_matches("0,30 * * * *", datetime(2026, 8, 5, 10, 15))

    def test_bad_expressions(self):
        assert not sched.cron_matches("")
        assert not sched.cron_matches("not a cron")
        assert not sched.cron_matches("* * * *")  # 4 fields


class TestSchedulerTick:
    async def test_tick_fires_scheduled_workflow_once_per_minute(
        self, db_session: FirestoreDB, test_user: dict, monkeypatch
    ):
        from app.schemas.workspace import WorkspaceCreate
        from app.services import workspace_service

        ws = await workspace_service.create_workspace(
            db_session, WorkspaceCreate(name="Sched WS"), owner=test_user
        )
        wf = await workflow_service.create_workflow(
            db_session,
            ws["id"],
            WorkflowCreate(
                name="Daily",
                trigger_type="schedule",
                schedule_cron="* * * * *",
                dag_definition={"nodes": [{"id": "a1", "type": "agent", "name": "Nope"}], "edges": []},
            ),
        )
        wf["status"] = WorkflowStatus.ACTIVE.value
        db_session.set(workflow_service.WORKFLOWS, wf["id"], wf)

        # Don't actually schedule background runs in the test.
        monkeypatch.setattr(sched, "_schedule", lambda db, fn: None)

        assert await sched.scheduler_tick(db_session) == 1
        assert await sched.scheduler_tick(db_session) == 0  # same minute → no dup

        execs, total = await workflow_service.list_executions(db_session, wf["id"])
        assert total == 1
        assert execs[0]["triggered_by"] == "scheduler"
        assert execs[0]["status"] == "running"

    async def test_tick_skips_non_schedule_and_inactive(
        self, db_session: FirestoreDB, test_user: dict, monkeypatch
    ):
        from app.schemas.workspace import WorkspaceCreate
        from app.services import workspace_service

        ws = await workspace_service.create_workspace(
            db_session, WorkspaceCreate(name="Sched WS 2"), owner=test_user
        )
        monkeypatch.setattr(sched, "_schedule", lambda db, fn: None)

        # Draft (not active) scheduled workflow → skipped.
        wf = await workflow_service.create_workflow(
            db_session,
            ws["id"],
            WorkflowCreate(
                name="Draft", trigger_type="schedule", schedule_cron="* * * * *",
                dag_definition={"nodes": [{"id": "a1", "type": "agent", "name": "Nope"}], "edges": []},
            ),
        )
        assert await sched.scheduler_tick(db_session) == 0
        execs, total = await workflow_service.list_executions(db_session, wf["id"])
        assert total == 0


# ─── Webhook triggers ────────────────────────────────


class TestWebhookTrigger:
    async def test_webhook_full_flow(
        self, client, auth_headers: dict, test_workspace: dict
    ):
        # Create a webhook-triggered workflow.
        r = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            json={
                "name": "Webhook WF",
                "trigger_type": "webhook",
                "dag_definition": {
                    "nodes": [{"id": "a1", "type": "agent", "name": "Nope"}],
                    "edges": [],
                },
            },
            headers=auth_headers,
        )
        assert r.status_code == 201
        wf = r.json()

        # Activate it (execution requires 'active').
        r2 = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        assert r2.status_code == 200

        # Get (lazily generates) the webhook token.
        r3 = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/webhook-token",
            headers=auth_headers,
        )
        assert r3.status_code == 200
        body = r3.json()
        token = body["token"]
        assert body["webhook_path"] == f"/api/v1/webhooks/{token}"

        # Fire it — no auth required (the token IS the secret).
        r4 = await client.post(f"/api/v1/webhooks/{token}", json={"payload": {"msg": "hi"}})
        assert r4.status_code == 202
        assert r4.json()["workflow_id"] == wf["id"]

        # Unknown token → 404.
        r5 = await client.post("/api/v1/webhooks/not-a-real-token", json={})
        assert r5.status_code == 404

        # An execution was created and triggered by 'webhook'.
        r6 = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/executions",
            headers=auth_headers,
        )
        assert len(r6.json()) == 1
        assert r6.json()[0]["triggered_by"] == "webhook"

    async def test_webhook_token_is_stable(
        self, client, auth_headers: dict, test_workspace: dict
    ):
        r = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            json={
                "name": "Webhook WF 2",
                "trigger_type": "webhook",
                "dag_definition": {
                    "nodes": [{"id": "a1", "type": "agent", "name": "Nope"}],
                    "edges": [],
                },
            },
            headers=auth_headers,
        )
        wf = r.json()
        r1 = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/webhook-token",
            headers=auth_headers,
        )
        r2 = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf['id']}/webhook-token",
            headers=auth_headers,
        )
        assert r1.json()["token"] == r2.json()["token"]


# ─── Autonomous tool use ─────────────────────────────


class TestAutonomousToolUse:
    async def test_agent_runs_tool_loop(
        self, db_session: FirestoreDB, test_user: dict, monkeypatch
    ):
        from app.schemas.workspace import WorkspaceCreate
        from app.services import execution_engine as ee, workspace_service

        ws = await workspace_service.create_workspace(
            db_session, WorkspaceCreate(name="Tool WS"), owner=test_user
        )
        tool = await tool_service.create_tool(
            db_session,
            ToolCreate(
                name="Echo", slug="echo", description="echoes",
                tool_type=ToolType.CUSTOM,
                source="https://example.test/api",
                parameters={"method": "GET", "url_template": "/echo/{msg}"},
                auth_type=ToolAuthType.NONE,
            ),
            workspace_id=ws["id"],
        )
        agent = await agent_service.create_agent(
            db_session,
            ws["id"],
            AgentCreate(
                name="Tool Agent",
                system_prompt="Use tools when needed.",
                model_provider="groq",
                model_name="llama-3.3-70b-versatile",
                tool_ids=[tool["id"]],
            ),
        )
        agent["status"] = AgentStatus.ACTIVE.value
        db_session.set(agent_service.AGENTS, agent["id"], agent)

        # Fake gateway: 1st call requests a tool call, 2nd answers.
        calls = {"n": 0}

        async def fake_raw(db, request, workspace_id=None, agent_id=None,
                           execution_id=None, preferred_provider=None, tools=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return {
                    "provider": "groq", "model": "llama-3.3-70b-versatile",
                    "message": {
                        "content": None,
                        "tool_calls": [{
                            "id": "call_1", "type": "function",
                            "function": {"name": "echo", "arguments": "{\"msg\": \"hello\"}"},
                        }],
                    },
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
                    "cost_usd": 0.0001,
                }
            return {
                "provider": "groq", "model": "llama-3.3-70b-versatile",
                "message": {"content": "Done: hello", "role": "assistant"},
                "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
                "cost_usd": 0.0002,
            }

        monkeypatch.setattr(ee.mcp_service, "route_chat_completion_raw", fake_raw)

        # Fake tool HTTP transport.
        class FakeResp:
            status_code = 200

            def json(self):
                return {"echo": "hello"}

        class FakeClient:
            def __init__(self, timeout=60):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def request(self, *a, **kw):
                return FakeResp()

        monkeypatch.setattr("httpx.AsyncClient", FakeClient)

        from app.schemas.agent import AgentExecutionCreate

        execution = await agent_service.create_execution(
            db_session, agent["id"], AgentExecutionCreate(input_data={"input": "please echo hello"})
        )
        execution = await agent_service.start_execution(db_session, execution)
        await ee.run_agent_execution(db_session, execution["id"])

        done = await agent_service.get_execution_by_id(db_session, execution["id"])
        assert done["status"] == ExecutionStatus.COMPLETED.value
        assert done["output_data"]["response"] == "Done: hello"
        steps = done["output_data"]["tool_steps"]
        assert len(steps) == 1
        assert steps[0]["tool"] == "echo"
        assert steps[0]["ok"] is True
        assert calls["n"] == 2  # LLM called twice (tool round-trip)

    def test_tool_to_openai_schema_derives_placeholders(self):
        from app.services.execution_engine import _tool_to_openai_schema

        schema = _tool_to_openai_schema({
            "id": "t1", "slug": "echo", "name": "Echo", "description": "d",
            "parameters": {"method": "GET", "url_template": "/echo/{msg}"},
        })
        assert schema["function"]["name"] == "echo"
        assert schema["function"]["parameters"]["type"] == "object"
        assert schema["function"]["description"] == "d"
        # The real argument (msg) is exposed — NOT implementation fields.
        assert "msg" in schema["function"]["parameters"]["properties"]
        assert "url_template" not in schema["function"]["parameters"]["properties"]
        assert "method" not in schema["function"]["parameters"]["properties"]

    def test_tool_to_openai_schema_uses_defined_schema(self):
        from app.services.execution_engine import _tool_to_openai_schema

        schema = _tool_to_openai_schema({
            "id": "t1", "slug": "fetch", "name": "Fetch", "description": "d",
            "schema_definition": {
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                }
            },
        })
        assert schema["function"]["parameters"]["required"] == ["url"]


# ─── API-key verification ────────────────────────────


class TestApiKeyVerification:
    async def test_verify_valid_uses_active_non_expired(
        self, db_session: FirestoreDB, test_user: dict
    ):
        from app.schemas.user import ApiKeyCreate
        from app.services import api_key_service

        record, full_key = await api_key_service.create_api_key(
            db_session, test_user["id"], ApiKeyCreate(name="mcp-key")
        )
        assert full_key.startswith("agos_")
        assert api_key_service.verify_api_key(db_session, full_key) is not None
        assert api_key_service.verify_api_key(db_session, "agos_0_bad") is None
        assert api_key_service.verify_api_key(db_session, "") is None

        # Revoked keys must fail.
        await api_key_service.revoke_api_key(db_session, record["id"], test_user["id"])
        assert api_key_service.verify_api_key(db_session, full_key) is None


# ─── MCP protocol server tools ───────────────────────


class TestMcpTools:
    async def test_list_workspaces_and_tools(
        self, db_session: FirestoreDB, test_user: dict, monkeypatch
    ):
        from app.schemas.workspace import WorkspaceCreate
        from app.services import mcp_server, workspace_service

        ws = await workspace_service.create_workspace(
            db_session, WorkspaceCreate(name="MCP WS"), owner=test_user
        )
        monkeypatch.setattr(mcp_server, "FirestoreDB", lambda: db_session)

        workspaces = await mcp_server.list_workspaces()
        assert any(w["id"] == ws["id"] and w["name"] == "MCP WS" for w in workspaces)

        tools = await mcp_server.list_tools(ws["id"])
        assert isinstance(tools, list)

    async def test_run_agent_tool(
        self, db_session: FirestoreDB, test_user: dict, monkeypatch
    ):
        from app.schemas.workspace import WorkspaceCreate
        from app.services import mcp_server, workspace_service

        ws = await workspace_service.create_workspace(
            db_session, WorkspaceCreate(name="MCP WS 2"), owner=test_user
        )
        agent = await agent_service.create_agent(
            db_session,
            ws["id"],
            AgentCreate(name="MCP Agent", model_provider="groq", model_name="llama-3.3-70b-versatile"),
        )
        agent["status"] = AgentStatus.ACTIVE.value
        db_session.set(agent_service.AGENTS, agent["id"], agent)

        monkeypatch.setattr(mcp_server, "FirestoreDB", lambda: db_session)

        async def fake_raw(db, request, workspace_id=None, agent_id=None,
                           execution_id=None, preferred_provider=None, tools=None):
            return {
                "provider": "groq", "model": "llama-3.3-70b-versatile",
                "message": {"content": "MCP answer", "role": "assistant"},
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
                "cost_usd": 0.0,
            }

        from app.services import execution_engine as ee
        monkeypatch.setattr(ee.mcp_service, "route_chat_completion_raw", fake_raw)
        # No tools on this agent → engine uses route_chat_completion; patch it too.
        from app.services.mcp_service import route_chat_completion  # noqa: F401

        async def fake_completion(db, request, workspace_id=None, agent_id=None,
                                  execution_id=None, use_fallback=True, preferred_provider=None):
            from app.schemas.mcp import ChatCompletionResponse
            from app.models.mcp import LLMProvider
            return ChatCompletionResponse(
                id="chatcmpl-mcp", model=request.model, provider=preferred_provider or LLMProvider.GROQ,
                choices=[{"index": 0, "message": {"role": "assistant", "content": "MCP answer"}, "finish_reason": "stop"}],
                usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
                cost_usd=0.0, created=datetime.now(),
            )

        monkeypatch.setattr(ee.mcp_service, "route_chat_completion", fake_completion)

        result = await mcp_server.run_agent(ws["id"], "MCP Agent", "hello")
        assert result["ok"] is True
        assert result["response"] == "MCP answer"
        assert result["status"] == "completed"
