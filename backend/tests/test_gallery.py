"""Gallery: publish, browse, and clone community agents (Firestore-backed)."""


async def _create_agent(client, auth_headers, workspace_id, name="Gallery Agent"):
    resp = await client.post(
        f"/api/v1/workspaces/{workspace_id}/agents/",
        json={
            "name": name,
            "description": "A public agent",
            "system_prompt": "You are helpful.",
            "model_name": "gpt-4o-mini",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def _publish_active_agent(client, auth_headers, workspace_id, agent_id):
    """Activate + publish an agent; returns the publish response."""
    resp = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/agents/{agent_id}",
        json={"status": "active"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    resp = await client.post(
        f"/api/v1/workspaces/{workspace_id}/agents/{agent_id}/publish",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()


async def test_gallery_is_public_and_empty_for_guests(client):
    """The public gallery endpoint is reachable without auth (guest mode)."""
    resp = await client.get("/api/v1/gallery/")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_cannot_publish_a_draft_agent(client, auth_headers, test_workspace):
    """Only ACTIVE agents may be published to the public gallery."""
    agent = await _create_agent(client, auth_headers, test_workspace["id"])
    resp = await client.post(
        f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/publish",
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "active" in resp.json()["detail"].lower()


async def test_publish_then_browse_as_guest(client, auth_headers, test_workspace):
    agent = await _create_agent(client, auth_headers, test_workspace["id"])
    published = await _publish_active_agent(
        client, auth_headers, test_workspace["id"], agent["id"]
    )
    assert published["published"] is True
    assert published["published_at"] is not None

    # Public listing shows it with author + workspace metadata (no auth).
    resp = await client.get("/api/v1/gallery/")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["id"] == agent["id"]
    # Username is derived from the email prefix (test@example.com -> "test").
    assert rows[0]["author_username"] == "test"
    assert rows[0]["workspace_name"] == "Test Workspace"
    assert rows[0]["model_name"] == "gpt-4o-mini"

    # Single-agent public view works too.
    resp = await client.get(f"/api/v1/gallery/{agent['id']}")
    assert resp.status_code == 200
    assert resp.json()["system_prompt"] == "You are helpful."


async def test_unpublish_removes_from_gallery(client, auth_headers, test_workspace):
    agent = await _create_agent(client, auth_headers, test_workspace["id"])
    await _publish_active_agent(client, auth_headers, test_workspace["id"], agent["id"])

    resp = await client.delete(
        f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/publish",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["published"] is False

    assert (await client.get("/api/v1/gallery/")).json() == []
    resp = await client.get(f"/api/v1/gallery/{agent['id']}")
    assert resp.status_code == 404


async def test_clone_into_second_users_workspace(client, auth_headers, second_user, test_workspace):
    agent = await _create_agent(client, auth_headers, test_workspace["id"])
    await _publish_active_agent(client, auth_headers, test_workspace["id"], agent["id"])

    resp = await client.post(
        f"/api/v1/gallery/{agent['id']}/clone",
        headers=second_user["auth_headers"],
    )
    assert resp.status_code == 201
    clone = resp.json()
    assert clone["id"] != agent["id"]
    assert clone["name"] == agent["name"]
    assert clone["status"] == "draft"
    assert clone["published"] is False

    # The clone lands in the second user's own workspace.
    workspaces = await client.get("/api/v1/workspaces/", headers=second_user["auth_headers"])
    assert workspaces.status_code == 200
    ws_ids = {w["id"] for w in workspaces.json()}
    assert clone["workspace_id"] in ws_ids


async def test_clone_strips_secrets_and_tools(client, auth_headers, second_user, test_workspace):
    """Secrets and tool bindings are workspace-scoped and never copied."""
    agent = await _create_agent(client, auth_headers, test_workspace["id"])
    resp = await client.patch(
        f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}",
        json={
            "status": "active",
            "tool_ids": ["tool-1"],
            "config": {"injected_secrets": ["sec-1"], "temperature_override": 0.2},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    await client.post(
        f"/api/v1/workspaces/{test_workspace['id']}/agents/{agent['id']}/publish",
        headers=auth_headers,
    )

    resp = await client.post(
        f"/api/v1/gallery/{agent['id']}/clone",
        headers=second_user["auth_headers"],
    )
    assert resp.status_code == 201
    clone = resp.json()
    assert clone["tool_ids"] == []
    clone_config = clone["config"] or {}
    assert "injected_secrets" not in clone_config
    # Non-secret config survives the clone.
    assert clone_config.get("temperature_override") == 0.2


async def test_clone_requires_auth(client, auth_headers, test_workspace):
    agent = await _create_agent(client, auth_headers, test_workspace["id"])
    await _publish_active_agent(client, auth_headers, test_workspace["id"], agent["id"])

    resp = await client.post(f"/api/v1/gallery/{agent['id']}/clone")
    assert resp.status_code == 401
