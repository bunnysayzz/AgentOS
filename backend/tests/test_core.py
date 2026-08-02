"""Integration tests for core CRUD domains: Workspaces, Agents, Tools."""

import pytest
from httpx import AsyncClient


# ─── Workspace Tests ─────────────────────────────────


class TestWorkspaces:
    async def test_create_workspace(self, client: AsyncClient, auth_headers: dict):
        """Should create a workspace."""
        response = await client.post(
            "/api/v1/workspaces/",
            json={"name": "My Workspace", "description": "Testing creation"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Workspace"
        assert data["slug"] == "my-workspace"

    async def test_list_workspaces(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list user's workspaces."""
        response = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_workspace(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should get workspace by ID."""
        response = await client.get(f"/api/v1/workspaces/{test_workspace['id']}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == test_workspace["name"]

    async def test_get_workspace_not_found(self, client: AsyncClient, auth_headers: dict):
        """Should return 404 for non-existent workspace."""
        import uuid
        response = await client.get(f"/api/v1/workspaces/{uuid.uuid4()}", headers=auth_headers)
        assert response.status_code == 404

    async def test_update_workspace(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should update workspace name."""
        response = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    async def test_update_workspace_not_admin(self, client: AsyncClient, second_user: dict, test_workspace: dict):
        """Should reject non-admin workspace update."""
        response = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}",
            json={"name": "Hacked"},
            headers=second_user["auth_headers"],
        )
        assert response.status_code == 403

    async def test_delete_workspace(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should soft-delete a workspace (owner only)."""
        response = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}",
            headers=auth_headers,
        )
        assert response.status_code == 204

    async def test_list_members(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list workspace members."""
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


# ─── Agent Tests ─────────────────────────────────────


class TestAgents:
    async def test_create_agent(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should create an agent in a workspace."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/",
            json={"name": "Test Agent", "description": "An agent for testing", "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Agent"
        assert data["status"] == "draft"

    async def test_list_agents(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list agents in a workspace."""
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/",
            json={"name": "Agent 1", "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_create_agent_with_system_prompt(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should create agent with system prompt."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/",
            json={
                "name": "Prompted Agent",
                "system_prompt": "You are a helpful assistant.",
                "model_name": "gpt-4o",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Prompted Agent"

    async def test_get_agent(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should get agent by ID."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/",
            json={"name": "Gettable Agent", "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        agent_id = create_resp.json()["id"]
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Gettable Agent"

    async def test_delete_agent(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should soft-delete an agent."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/",
            json={"name": "Deletable Agent", "model_name": "gpt-4o"},
            headers=auth_headers,
        )
        agent_id = create_resp.json()["id"]
        response = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204


# ─── Tool Tests ──────────────────────────────────────


class TestTools:
    async def test_create_tool(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should create a tool in a workspace."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "Test Tool", "slug": "test-tool", "description": "A tool for testing"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Tool"

    async def test_list_tools(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list workspace tools."""
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "Tool 1", "slug": "tool-1"},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    async def test_create_tool_non_admin(self, client: AsyncClient, second_user: dict, test_workspace: dict):
        """Should reject non-admin from creating tools."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "Unauthorized Tool", "slug": "unauth-tool"},
            headers=second_user["auth_headers"],
        )
        assert response.status_code == 403

    async def test_get_tool(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should get a tool by ID."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "Gettable Tool", "slug": "gettable-tool"},
            headers=auth_headers,
        )
        tool_id = create_resp.json()["id"]
        response = await client.get(f"/api/v1/tools/{tool_id}", headers=auth_headers)
        assert response.status_code == 200

    async def test_delete_tool(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should soft-delete a tool."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "Deletable Tool", "slug": "deletable-tool"},
            headers=auth_headers,
        )
        tool_id = create_resp.json()["id"]
        response = await client.delete(f"/api/v1/tools/{tool_id}", headers=auth_headers)
        assert response.status_code == 204


# ─── Prompt Tests ────────────────────────────────────


class TestPrompts:
    async def test_create_prompt(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should create a prompt in a workspace."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts",
            json={
                "name": "Test Prompt",
                "slug": "test-prompt",
                "initial_content": "You are a {{role}} assistant.",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Prompt"
        assert data["current_version"] >= 1

    async def test_create_version(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should create a new version of a prompt."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts",
            json={"name": "Versioned Prompt", "slug": "versioned-prompt", "initial_content": "v1"},
            headers=auth_headers,
        )
        prompt_id = create_resp.json()["id"]
        response = await client.post(
            f"/api/v1/prompts/{prompt_id}/versions",
            json={"content": "v2 content"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["version"] == 2

    async def test_list_prompts(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list prompts in a workspace."""
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts",
            json={"name": "Listable Prompt", "slug": "listable-prompt"},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1


# ─── Secret Tests ────────────────────────────────────


class TestSecrets:
    async def test_create_secret(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should create an encrypted secret."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            json={"name": "API Key", "slug": "api_key", "value": "sk-1234567890"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Key"
        # Value should NEVER be returned
        assert "value" not in data

    async def test_list_secrets(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list secrets without returning values."""
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            json={"name": "Secret Key", "slug": "secret_key", "value": "sk-test"},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        for secret in response.json():
            assert "encrypted_value" not in secret
            assert "value" not in secret

    async def test_delete_secret(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should soft-delete a secret."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            json={"name": "Delete Me", "slug": "delete_me", "value": "sk-del"},
            headers=auth_headers,
        )
        secret_id = create_resp.json()["id"]
        response = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/{secret_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204


# ─── Artifact Tests ──────────────────────────────────


class TestArtifacts:
    async def test_create_artifact(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should register an artifact."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            json={"name": "config.json", "content_type": "application/json"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["name"] == "config.json"

    async def test_list_artifacts(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list artifacts."""
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            json={"name": "data.txt", "content_type": "text/plain"},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_delete_artifact(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should soft-delete an artifact."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            json={"name": "old.log", "content_type": "text/plain"},
            headers=auth_headers,
        )
        artifact_id = create_resp.json()["id"]
        response = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/{artifact_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204


# ─── Workflow Tests ──────────────────────────────────


class TestWorkflows:
    async def test_create_workflow(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should create a workflow."""
        response = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            json={"name": "Test Workflow", "description": "A test workflow"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Test Workflow"
        assert response.json()["status"] == "draft"

    async def test_list_workflows(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should list workflows."""
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            json={"name": "WF 1"},
            headers=auth_headers,
        )
        response = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    async def test_delete_workflow(self, client: AsyncClient, auth_headers: dict, test_workspace: dict):
        """Should soft-delete a workflow."""
        create_resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/",
            json={"name": "Delete WF"},
            headers=auth_headers,
        )
        wf_id = create_resp.json()["id"]
        response = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/workflows/{wf_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204
