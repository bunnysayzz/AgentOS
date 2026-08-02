"""Agent domain integration tests: CRUD, versioning, and execution lifecycle."""

import uuid


async def _create_agent(client, headers, ws_id, **overrides):
    payload = {"name": "Test Agent", "model_name": "gpt-4o", **overrides}
    resp = await client.post(f"/api/v1/workspaces/{ws_id}/agents/", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()


class TestAgentCRUD:
    async def test_create_agent_defaults(self, client, auth_headers, test_workspace):
        data = await _create_agent(client, auth_headers, test_workspace["id"])
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert data["model_provider"] == "openai"
        assert data["model_name"] == "gpt-4o"
        assert data["temperature"] == 0.7

    async def test_create_agent_requires_member_role(self, client, auth_headers, second_user, test_workspace):
        # second_user is not a member -> 403
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/",
            json={"name": "Nope", "model_name": "gpt-4o"},
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403

    async def test_list_agents(self, client, auth_headers, test_workspace):
        await _create_agent(client, auth_headers, test_workspace["id"], name="Agent A")
        await _create_agent(client, auth_headers, test_workspace["id"], name="Agent B")
        resp = await client.get(f"/api/v1/workspaces/{test_workspace['id']}/agents/", headers=auth_headers)
        assert resp.status_code == 200
        names = [a["name"] for a in resp.json()]
        assert "Agent A" in names and "Agent B" in names

    async def test_get_agent(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == agent["id"]

    async def test_get_agent_from_other_workspace_404(self, client, auth_headers, second_user, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        other_ws = await client.post(
            "/api/v1/workspaces/", json={"name": "Other WS"}, headers=second_user["auth_headers"]
        )
        resp = await client.get(
            f"/api/v1/workspaces/{other_ws.json()['id']}/agents/{agent['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 404

    async def test_update_name_keeps_version(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            json={"name": "Renamed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"
        assert resp.json()["version"] == 1

    async def test_config_change_bumps_version(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            json={"system_prompt": "You are a reviewer.", "temperature": 0.2},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    async def test_delete_agent_archives(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 204
        # Deleted agents no longer listed
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/", headers=auth_headers
        )
        assert agent["id"] not in [a["id"] for a in listing.json()]


class TestAgentExecutionLifecycle:
    async def test_execute_requires_active(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/execute",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400  # draft cannot execute

    async def test_activate_then_execute_creates_pending(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/execute",
            json={"input_data": {"question": "hi"}},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["input_data"] == {"question": "hi"}
        assert data["session_id"] is not None

    async def test_full_lifecycle_start_pause_resume_cancel(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        exec_data = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/execute",
                json={},
                headers=auth_headers,
            )
        ).json()
        eid = exec_data["id"]
        base = f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/executions/{eid}"

        # pending -> running
        r = await client.post(f"{base}/start", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "running"

        # running -> paused
        r = await client.post(f"{base}/pause", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "paused"

        # paused -> running
        r = await client.post(f"{base}/resume", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "running"

        # running -> cancelled
        r = await client.post(f"{base}/cancel", headers=auth_headers)
        assert r.status_code == 200 and r.json()["status"] == "cancelled"

    async def test_invalid_transitions_rejected(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        eid = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/execute",
                json={},
                headers=auth_headers,
            )
        ).json()["id"]
        base = f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/executions/{eid}"

        # Cannot pause a pending execution
        r = await client.post(f"{base}/pause", headers=auth_headers)
        assert r.status_code == 400

        # Cannot start twice
        await client.post(f"{base}/start", headers=auth_headers)
        r = await client.post(f"{base}/start", headers=auth_headers)
        assert r.status_code == 400

        # Cannot resume a running execution
        r = await client.post(f"{base}/resume", headers=auth_headers)
        assert r.status_code == 400

    async def test_list_and_get_executions(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/execute",
            json={},
            headers=auth_headers,
        )
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/executions",
            headers=auth_headers,
        )
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    async def test_session_executions(self, client, auth_headers, test_workspace):
        agent = await _create_agent(client, auth_headers, test_workspace["id"])
        await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
            json={"status": "active"},
            headers=auth_headers,
        )
        e1 = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/execute",
                json={"session_id": "sess-123"},
                headers=auth_headers,
            )
        ).json()
        e2 = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/execute",
                json={"session_id": "sess-123"},
                headers=auth_headers,
            )
        ).json()
        assert e1["session_id"] == e2["session_id"] == "sess-123"
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/agents/sessions/sess-123/executions",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2
