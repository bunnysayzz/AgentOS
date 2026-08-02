"""Execution Graph integration tests: node-level tracing via the service + API."""

import uuid
from uuid import UUID

import pytest

from app.services import execution_graph_service
from app.models.execution_graph import NodeType, NodeStatus


async def _create_execution(client, auth_headers, ws_id):
    agent = (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/agents/",
            json={"name": "Graph Agent", "model_name": "gpt-4o"},
            headers=auth_headers,
        )
    ).json()
    await client.patch(
        f"/api/v1/workspaces/{ws_id}/agents/{agent['id']}",
        json={"status": "active"},
        headers=auth_headers,
    )
    return (
        await client.post(
            f"/api/v1/workspaces/{ws_id}/agents/{agent['id']}/execute",
            json={},
            headers=auth_headers,
        )
    ).json()


class TestExecutionGraph:
    async def test_empty_graph(self, client, auth_headers, test_workspace):
        execution = await _create_execution(client, auth_headers, test_workspace["id"])
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/executions/{execution['id']}/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["total_tokens"] == 0

    async def test_graph_with_nodes(self, client, auth_headers, test_workspace, db_session):
        execution = await _create_execution(client, auth_headers, test_workspace["id"])
        eid = execution["id"]

        node = await execution_graph_service.create_node(
            db_session,
            execution_id=UUID(eid),
            node_type=NodeType.LLM_CALL,
            node_name="gpt-4o call",
            input_data={"prompt": "hi"},
            model_provider="openai",
            model_name="gpt-4o",
        )
        await execution_graph_service.update_node_status(
            db_session,
            node,
            status=NodeStatus.COMPLETED,
            output_data={"answer": "hi there"},
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.0004,
        )

        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/executions/{eid}/graph",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert data["total_tokens"] == 15
        assert data["total_cost_usd"] == pytest.approx(0.0004)
        assert data["nodes"][0]["node_type"] == "llm_call"
        assert data["nodes"][0]["status"] == "completed"

    async def test_list_nodes_endpoint(self, client, auth_headers, test_workspace, db_session):
        execution = await _create_execution(client, auth_headers, test_workspace["id"])
        eid = execution["id"]
        await execution_graph_service.create_node(
            db_session, execution_id=UUID(eid), node_type=NodeType.TOOL_CALL, node_name="fetch"
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/executions/{eid}/graph/nodes",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_get_node_by_id(self, client, auth_headers, test_workspace, db_session):
        execution = await _create_execution(client, auth_headers, test_workspace["id"])
        eid = execution["id"]
        node = await execution_graph_service.create_node(
            db_session, execution_id=UUID(eid), node_type=NodeType.FUNCTION, node_name="compute"
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/executions/{eid}/graph/nodes/{node.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["node_name"] == "compute"

    async def test_get_node_404_for_other_execution(self, client, auth_headers, test_workspace, db_session):
        execution = await _create_execution(client, auth_headers, test_workspace["id"])
        node = await execution_graph_service.create_node(
            db_session,
            execution_id=UUID(execution["id"]),
            node_type=NodeType.LLM_CALL,
            node_name="x",
        )
        other_execution = await _create_execution(client, auth_headers, test_workspace["id"])
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/executions/{other_execution['id']}/graph/nodes/{node.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_graph_requires_workspace_access(self, client, auth_headers, second_user, test_workspace):
        execution = await _create_execution(client, auth_headers, test_workspace["id"])
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/executions/{execution['id']}/graph",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403