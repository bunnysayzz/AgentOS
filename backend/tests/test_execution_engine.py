"""Tests for the Execution Engine: agent runs, tool runs, workflow DAG runs.

Uses the in-memory FakeFirestore + monkeypatched MCP gateway so no real LLM
or HTTP call is made.
"""

import asyncio

import pytest

from app.core.db import FirestoreDB
from app.models.agent import AgentStatus, ExecutionStatus
from app.models.execution_graph import NodeStatus
from app.models.workflow import WorkflowStatus, WorkflowExecutionStatus
from app.models.tool import ToolType, ToolAuthType
from app.schemas.agent import AgentCreate
from app.schemas.workflow import WorkflowCreate
from app.schemas.tool import ToolCreate
from app.services import (
    agent_service,
    execution_graph_service,
    tool_service,
    workflow_service,
)


# ─── Fake MCP gateway ─────────────────────────────────


async def fake_route_chat_completion(
    db, request, workspace_id=None, agent_id=None, execution_id=None,
    use_fallback=True, preferred_provider=None,
):
    """Canned gateway response — no real LLM call."""
    from app.schemas.mcp import ChatCompletionResponse
    from app.models.mcp import LLMProvider
    from datetime import datetime, timezone

    return ChatCompletionResponse(
        id="chatcmpl-fake",
        model=request.model,
        provider=preferred_provider or LLMProvider.GROQ,
        choices=[{"index": 0, "message": {"role": "assistant", "content": "Hello from fake LLM"}, "finish_reason": "stop"}],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        cost_usd=0.0001,
        created=datetime.now(timezone.utc),
    )


@pytest.fixture(autouse=True)
def fake_gateway(monkeypatch):
    from app.services import execution_engine as ee
    monkeypatch.setattr(ee.mcp_service, "route_chat_completion", fake_route_chat_completion)


# ─── Fixtures: agent + workflow + tool in a workspace ──


@pytest.fixture
async def ws(db_session: FirestoreDB, test_user: dict):
    from app.schemas.workspace import WorkspaceCreate
    from app.services import workspace_service
    ws = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="Engine WS", description="execution engine tests"),
        owner=test_user,
    )
    return ws


@pytest.fixture
async def agent(db_session: FirestoreDB, ws: dict):
    created = await agent_service.create_agent(
        db_session,
        ws["id"],
        AgentCreate(
            name="Engine Agent",
            description="test agent",
            system_prompt="You are a test agent.",
            model_provider="groq",
            model_name="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=256,
        ),
    )
    created["status"] = AgentStatus.ACTIVE.value
    db_session.set(agent_service.AGENTS, created["id"], created)
    return created


@pytest.fixture
async def tool(db_session: FirestoreDB, ws: dict):
    created = await tool_service.create_tool(
        db_session,
        ToolCreate(
            name="Echo Tool",
            slug="echo-tool",
            description="echoes params",
            tool_type=ToolType.CUSTOM,
            source="https://example.test/api",
            parameters={"method": "GET", "url_template": "/echo/{msg}"},
            auth_type=ToolAuthType.NONE,
            is_public=False,
        ),
        workspace_id=ws["id"],
    )
    return created


@pytest.fixture
async def workflow(db_session: FirestoreDB, ws: dict):
    created = await workflow_service.create_workflow(
        db_session,
        ws["id"],
        WorkflowCreate(
            name="Engine Pipeline",
            description="agent -> tool",
            trigger_type="manual",
            dag_definition={
                "nodes": [
                    {"id": "a1", "type": "agent", "name": "Engine Agent"},
                    {"id": "t1", "type": "tool", "name": "Echo Tool"},
                ],
                "edges": [{"source": "a1", "target": "t1"}],
            },
        ),
    )
    created["status"] = WorkflowStatus.ACTIVE.value
    db_session.set(workflow_service.WORKFLOWS, created["id"], created)
    return created


# ─── Agent execution tests ────────────────────────────


class TestAgentExecution:
    async def test_agent_execution_completes_with_output(
        self, db_session: FirestoreDB, agent: dict
    ):
        from app.services.execution_engine import run_agent_execution

        execution = await agent_service.create_execution(
            db_session, agent["id"], None
        )
        execution = await agent_service.start_execution(db_session, execution)

        await run_agent_execution(db_session, execution["id"])

        done = await agent_service.get_execution_by_id(db_session, execution["id"])
        assert done["status"] == ExecutionStatus.COMPLETED.value
        assert done["output_data"]["response"] == "Hello from fake LLM"
        assert done["total_tokens"] == 15
        assert done["cost_usd"] == 0.0001

        nodes = await execution_graph_service.list_execution_nodes(
            db_session, execution["id"]
        )
        assert len(nodes) == 1
        assert nodes[0]["status"] == NodeStatus.COMPLETED.value
        assert nodes[0]["node_type"] == "agent_call"

    async def test_agent_execution_fails_when_agent_missing(
        self, db_session: FirestoreDB, ws: dict
    ):
        from app.services.execution_engine import run_agent_execution

        # Create an execution for a non-existent agent directly.
        created = await agent_service.get_execution_by_id(db_session, "missing")
        assert created is None

        # Orphan execution via low-level stamping:
        from app.core.db import stamp
        from app.models.agent import ExecutionStatus as ES

        orphan = stamp({
            "agent_id": "no-such-agent",
            "session_id": "s",
            "status": ES.RUNNING.value,
            "input_data": {"input": "hi"},
        })
        db_session.add(agent_service.EXECUTIONS, orphan)

        await run_agent_execution(db_session, orphan["id"])
        done = await agent_service.get_execution_by_id(db_session, orphan["id"])
        assert done["status"] == ExecutionStatus.FAILED.value

    async def test_agent_execution_skips_non_running(
        self, db_session: FirestoreDB, agent: dict
    ):
        from app.services.execution_engine import run_agent_execution

        execution = await agent_service.create_execution(db_session, agent["id"], None)
        # Still PENDING — engine should do nothing.
        await run_agent_execution(db_session, execution["id"])
        done = await agent_service.get_execution_by_id(db_session, execution["id"])
        assert done["status"] == ExecutionStatus.PENDING.value


# ─── Tool execution tests ─────────────────────────────


class TestToolExecution:
    async def test_run_tool_builds_url_and_records(self, db_session: FirestoreDB, tool: dict, monkeypatch):
        from app.services.execution_engine import run_tool

        captured = {}

        class FakeClient:
            def __init__(self, timeout=60):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def request(self, method, url, json=None, headers=None, params=None):
                captured["method"] = method
                captured["url"] = url
                captured["json"] = json
                return _FakeHTTPResponse()

        class _FakeHTTPResponse:
            status_code = 200

            def json(self):
                return {"echo": "ok"}

        monkeypatch.setattr("httpx.AsyncClient", FakeClient)

        output = await run_tool(db_session, tool, params={"msg": "hello"}, execution_id="exec-1")

        assert captured["method"] == "GET"
        assert captured["url"] == "https://example.test/api/echo/hello"
        assert output["ok"] is True

        execs, total = await tool_service.list_tool_executions(db_session, tool["id"])
        assert total == 1
        assert execs[0]["status"] == "success"

    async def test_run_tool_records_failure(self, db_session: FirestoreDB, tool: dict, monkeypatch):
        from app.services.execution_engine import run_tool

        class _FakeHTTPResponse:
            status_code = 500

            def json(self):
                return {"error": "boom"}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def request(self, *a, **kw):
                return _FakeHTTPResponse()

        monkeypatch.setattr("httpx.AsyncClient", FakeClient)

        output = await run_tool(db_session, tool, params={"msg": "x"}, execution_id="exec-2")
        assert output["ok"] is False

        execs, total = await tool_service.list_tool_executions(db_session, tool["id"])
        assert execs[0]["status"] == "failed"


# ─── Workflow DAG execution tests ─────────────────────


class TestWorkflowExecution:
    async def test_workflow_runs_all_nodes(
        self, db_session: FirestoreDB, workflow: dict, agent: dict, tool: dict, monkeypatch
    ):
        from app.services.execution_engine import run_workflow_execution

        class FakeResp:
            status_code = 200

            def json(self):
                return {"echo": "ok"}

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

        execution = await workflow_service.create_execution(
            db_session, workflow, input_data={"input": "go"}, triggered_by="tester"
        )
        execution = await workflow_service.start_execution(db_session, execution)

        await run_workflow_execution(db_session, execution["id"])

        done = await workflow_service.get_execution(db_session, execution["id"])
        assert done["status"] == WorkflowExecutionStatus.COMPLETED.value
        assert "a1" in done["output_data"]["results"]
        assert "t1" in done["output_data"]["results"]

        nodes = await execution_graph_service.list_execution_nodes(
            db_session, execution["id"]
        )
        types = {n["node_type"] for n in nodes}
        assert "agent_call" in types
        assert "tool_call" in types

    async def test_workflow_pauses_at_approval_gate(
        self, db_session: FirestoreDB, ws: dict, agent: dict
    ):
        from app.services.execution_engine import run_workflow_execution
        from app.schemas.workflow import WorkflowCreate

        wf = await workflow_service.create_workflow(
            db_session,
            ws["id"],
            WorkflowCreate(
                name="Approval Flow",
                dag_definition={
                    "nodes": [
                        {"id": "a1", "type": "agent", "name": "Engine Agent"},
                        {"id": "g1", "type": "approval_gate", "name": "Human Check"},
                        {"id": "a2", "type": "agent", "name": "Engine Agent"},
                    ],
                    "edges": [
                        {"source": "a1", "target": "g1"},
                        {"source": "g1", "target": "a2"},
                    ],
                },
            ),
        )
        wf["status"] = WorkflowStatus.ACTIVE.value
        db_session.set(workflow_service.WORKFLOWS, wf["id"], wf)

        execution = await workflow_service.create_execution(db_session, wf)
        execution = await workflow_service.start_execution(db_session, execution)

        await run_workflow_execution(db_session, execution["id"])

        done = await workflow_service.get_execution(db_session, execution["id"])
        assert done["status"] == WorkflowExecutionStatus.AWAITING_APPROVAL.value
        assert done["snapshot"]["pending_node"] == "g1"

        # Approve → resumes and runs the remaining node.
        execution = await workflow_service.approve_execution(db_session, done)
        await run_workflow_execution(db_session, execution["id"])
        final = await workflow_service.get_execution(db_session, execution["id"])
        assert final["status"] == WorkflowExecutionStatus.COMPLETED.value

    async def test_workflow_fails_on_missing_agent(
        self, db_session: FirestoreDB, ws: dict
    ):
        from app.services.execution_engine import run_workflow_execution

        wf = await workflow_service.create_workflow(
            db_session,
            ws["id"],
            WorkflowCreate(
                name="Broken Flow",
                dag_definition={
                    "nodes": [{"id": "x1", "type": "agent", "name": "Nonexistent Agent"}],
                    "edges": [],
                },
            ),
        )
        wf["status"] = WorkflowStatus.ACTIVE.value
        db_session.set(workflow_service.WORKFLOWS, wf["id"], wf)

        execution = await workflow_service.create_execution(db_session, wf)
        execution = await workflow_service.start_execution(db_session, execution)

        await run_workflow_execution(db_session, execution["id"])

        done = await workflow_service.get_execution(db_session, execution["id"])
        assert done["status"] == WorkflowExecutionStatus.FAILED.value
        assert "not found" in (done["error_message"] or "")


# ─── Provider encryption + test connection ────────────


class TestProviderService:
    async def test_fernet_roundtrip(self, db_session: FirestoreDB):
        from app.services.provider_service import (
            _decrypt_key,
            _encrypt_key,
            upsert_provider_config,
            get_provider_config,
        )
        from app.schemas.mcp import ProviderConfigCreate
        from app.models.mcp import LLMProvider

        cfg = await upsert_provider_config(
            db_session,
            ProviderConfigCreate(
                provider=LLMProvider.GROQ,
                api_key="gsk-super-secret-key-123",
                base_url="https://api.groq.com/openai/v1",
                default_model="llama-3.3-70b-versatile",
            ),
        )
        assert cfg["encrypted_api_key"].startswith("fernet:")
        stored = await get_provider_config(db_session, LLMProvider.GROQ)
        assert _decrypt_key(stored["encrypted_api_key"]) == "gsk-super-secret-key-123"

    async def test_legacy_xor_decrypt_backward_compat(self):
        from app.services.provider_service import _decrypt_key_legacy_xor, _encrypt_key  # noqa
        from app.core.config import settings

        # Simulate a legacy XOR value using the old scheme.
        key = settings.ENCRYPTION_KEY
        plain = "sk-legacy-xor-value-1"
        encrypted = []
        for i, c in enumerate(plain):
            k = ord(key[i % len(key)])
            encrypted.append(chr(ord(c) ^ k))
        import base64
        legacy = base64.b64encode("".join(encrypted).encode()).decode()

        assert _decrypt_key_legacy_xor(legacy) == plain

    async def test_openai_compatible_test_connection(
        self, db_session: FirestoreDB, monkeypatch
    ):
        from app.services.provider_service import (
            get_provider_config,
            test_connection,
            upsert_provider_config,
        )
        from app.schemas.mcp import ProviderConfigCreate
        from app.models.mcp import LLMProvider

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"data": [{"id": "gpt-4o"}]}

        class FakeClient:
            def __init__(self, timeout=10):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return FakeResponse()

        monkeypatch.setattr("httpx.AsyncClient", FakeClient)

        await upsert_provider_config(
            db_session,
            ProviderConfigCreate(
                provider=LLMProvider.CEREBRAS,
                api_key="csk-test-123",
                base_url="https://api.cerebras.ai/v1",
            ),
        )
        success, message = await test_connection(db_session, LLMProvider.CEREBRAS)
        assert success is True
        assert message == "Connection successful"

        # last_tested_at recorded on the stored config
        stored = await get_provider_config(db_session, LLMProvider.CEREBRAS)
        assert stored.get("last_tested_at") is not None
