"""Tool Registry integration tests: CRUD, public tools, scoping, and executions."""


class TestToolCRUD:
    async def test_create_tool_auto_slug(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "Fetch Data Tool", "description": "Fetches data"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["slug"] == "fetch-data-tool"
        assert data["is_active"] is True
        assert data["tool_type"] == "custom"

    async def test_create_requires_admin(self, client, auth_headers, second_user, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "No Access"},
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403

    async def test_duplicate_slug_conflict(self, client, auth_headers, test_workspace):
        payload = {"name": "Dup Tool", "slug": "dup-tool"}
        r1 = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools", json=payload, headers=auth_headers
        )
        assert r1.status_code == 201
        r2 = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools", json=payload, headers=auth_headers
        )
        assert r2.status_code == 409

    async def test_list_tools_includes_public(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "My Tool"},
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/tools", headers=auth_headers
        )
        assert resp.status_code == 200
        assert "My Tool" in [t["name"] for t in resp.json()]

    async def test_public_tool_visible_across_workspaces(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/tools",
            json={"name": "Shared Tool", "is_public": True},
            headers=auth_headers,
        )
        other_ws = (
            await client.post("/api/v1/workspaces/", json={"name": "Other WS"}, headers=second_user["auth_headers"])
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{other_ws['id']}/tools", headers=second_user["auth_headers"]
        )
        assert resp.status_code == 200
        assert "Shared Tool" in [t["name"] for t in resp.json()]

    async def test_get_tool_by_global_id(self, client, auth_headers, test_workspace):
        tool = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/tools",
                json={"name": "Gettable"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.get(f"/api/v1/tools/{tool['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Gettable"

    async def test_update_schema_bumps_version(self, client, auth_headers, test_workspace):
        tool = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/tools",
                json={"name": "Versioned Tool"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.patch(
            f"/api/v1/tools/{tool['id']}",
            json={"schema_definition": {"type": "object"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    async def test_non_admin_cannot_update(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "viewer"},
            headers=auth_headers,
        )
        tool = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/tools",
                json={"name": "Protected"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.patch(
            f"/api/v1/tools/{tool['id']}",
            json={"name": "Hacked"},
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403

    async def test_delete_tool_soft_delete(self, client, auth_headers, test_workspace):
        tool = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/tools",
                json={"name": "Deletable"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.delete(f"/api/v1/tools/{tool['id']}", headers=auth_headers)
        assert resp.status_code == 204
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/tools", headers=auth_headers
        )
        assert tool["id"] not in [t["id"] for t in listing.json()]

    async def test_tool_executions_empty_listing(self, client, auth_headers, test_workspace):
        tool = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/tools",
                json={"name": "Exec Tool"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.get(f"/api/v1/tools/{tool['id']}/executions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []
