"""Memory Engine integration tests: CRUD, session scoping, search, consolidation."""


class TestMemoryCRUD:
    async def test_store_and_list_memory(self, client, auth_headers, test_workspace):
        created = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/memory",
            json={"role": "user", "content": "Remember this fact", "session_id": "s1"},
            headers=auth_headers,
        )
        assert created.status_code == 201
        assert created.json()["content"] == "Remember this fact"

        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/memory", headers=auth_headers
        )
        assert listing.status_code == 200
        assert len(listing.json()) == 1

    async def test_session_scoped_memory(self, client, auth_headers, test_workspace):
        for sid, content in [("s1", "first"), ("s1", "second"), ("s2", "other")]:
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/memory",
                json={"role": "user", "content": content, "session_id": sid},
                headers=auth_headers,
            )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/memory/sessions/s1",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        contents = [e["content"] for e in resp.json()]
        assert "first" in contents and "second" in contents and "other" not in contents


class TestMemorySearch:
    async def test_keyword_search(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/memory",
            json={"role": "user", "content": "deployment config for kubernetes", "session_id": "s1"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/memory",
            json={"role": "user", "content": "shopping list: milk and eggs", "session_id": "s1"},
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/memory/search",
            params={"q": "kubernetes"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert "kubernetes" in results[0]["content"]

    async def test_search_respects_workspace_scope(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/memory",
            json={"role": "user", "content": "secret keyword alpha", "session_id": "s1"},
            headers=auth_headers,
        )
        other_ws = (
            await client.post("/api/v1/workspaces/", json={"name": "Other"}, headers=second_user["auth_headers"])
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{other_ws['id']}/memory/search",
            params={"q": "alpha"},
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestMemoryLifecycle:
    async def test_clear_session(self, client, auth_headers, test_workspace):
        for content in ["a", "b", "c"]:
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/memory",
                json={"role": "user", "content": content, "session_id": "clear-me"},
                headers=auth_headers,
            )
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/memory/sessions/clear-me",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 3
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/memory/sessions/clear-me",
            headers=auth_headers,
        )
        assert listing.json() == []

    async def test_delete_single_entry(self, client, auth_headers, test_workspace):
        entry = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/memory",
                json={"role": "user", "content": "delete me", "session_id": "s1"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.delete(f"/api/v1/memory/{entry['id']}", headers=auth_headers)
        assert resp.status_code == 204
        resp = await client.get(f"/api/v1/memory/{entry['id']}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_consolidation_trims_oldest(self, client, auth_headers, test_workspace):
        for i in range(12):
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/memory",
                json={"role": "user", "content": f"entry-{i}", "session_id": "consol"},
                headers=auth_headers,
            )
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/memory/consolidate",
            params={"session_id": "consol", "max_entries": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["consolidated"] == 2
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/memory/sessions/consol",
            headers=auth_headers,
        )
        remaining = [e["content"] for e in listing.json()]
        assert len(remaining) == 10
        assert "entry-0" not in remaining  # oldest trimmed
        assert "entry-11" in remaining  # newest kept
