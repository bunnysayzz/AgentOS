"""Tests for the demo workspace seeder (one-click first-run experience)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_seed_demo_creates_populated_workspace(
    client: AsyncClient, auth_headers: dict
):
    """Seeding creates a workspace with agents, workflow, prompts, tools, memory."""
    resp = await client.post("/api/v1/demo/seed", headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["slug"] == "demo-workspace"

    ws_id = data["id"]

    # Workspace visible to the user
    ws_list = await client.get("/api/v1/workspaces/", headers=auth_headers)
    assert any(w["id"] == ws_id for w in ws_list.json())

    # Agents seeded (endpoints return plain lists)
    agents = await client.get(
        f"/api/v1/workspaces/{ws_id}/agents", headers=auth_headers
    )
    agent_names = [a["name"] for a in agents.json()]
    assert "Support Hero" in agent_names
    assert "Brief Writer" in agent_names

    # Workflow seeded
    workflows = await client.get(
        f"/api/v1/workspaces/{ws_id}/workflows", headers=auth_headers
    )
    assert any(w["name"] == "Support Triage" for w in workflows.json())

    # Prompts seeded
    prompts = await client.get(
        f"/api/v1/workspaces/{ws_id}/prompts", headers=auth_headers
    )
    prompt_names = [p["name"] for p in prompts.json()]
    assert "Customer Reply" in prompt_names

    # Tools seeded
    tools = await client.get(f"/api/v1/workspaces/{ws_id}/tools", headers=auth_headers)
    tool_names = [t["name"] for t in tools.json()]
    assert "Search Knowledge Base" in tool_names
    assert "Slack Notify" in tool_names

    # Memory seeded
    memory = await client.get(
        f"/api/v1/workspaces/{ws_id}/memory", headers=auth_headers
    )
    assert len(memory.json()) >= 1


@pytest.mark.asyncio
async def test_seed_demo_is_idempotent(client: AsyncClient, auth_headers: dict):
    """Calling the seeder twice returns the same workspace, not a duplicate."""
    first = await client.post("/api/v1/demo/seed", headers=auth_headers)
    second = await client.post("/api/v1/demo/seed", headers=auth_headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    ws_list = await client.get("/api/v1/workspaces/", headers=auth_headers)
    demo_workspaces = [w for w in ws_list.json() if w["slug"] == "demo-workspace"]
    assert len(demo_workspaces) == 1


@pytest.mark.asyncio
async def test_seed_demo_requires_auth(client: AsyncClient):
    """Unauthenticated users cannot seed a demo workspace."""
    resp = await client.post("/api/v1/demo/seed")
    assert resp.status_code in (401, 403)
