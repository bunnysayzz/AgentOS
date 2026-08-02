"""Prompt Registry integration tests: versioning, rendering, rollback, public prompts."""


class TestPromptCRUD:
    async def test_create_prompt_with_initial_version(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts",
            json={
                "name": "Code Reviewer",
                "initial_content": "You are a {{role}} reviewer for {{language}}.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Code Reviewer"
        assert data["current_version"] == 1

    async def test_duplicate_slug_conflict(self, client, auth_headers, test_workspace):
        payload = {"name": "Dup Prompt", "slug": "dup-prompt", "initial_content": "x"}
        r1 = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts", json=payload, headers=auth_headers
        )
        assert r1.status_code == 201
        r2 = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts", json=payload, headers=auth_headers
        )
        assert r2.status_code == 409

    async def test_list_and_get(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts",
            json={"name": "Listable", "initial_content": "hi"},
            headers=auth_headers,
        )
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts", headers=auth_headers
        )
        assert listing.status_code == 200
        assert len(listing.json()) == 1
        pid = listing.json()[0]["id"]
        one = await client.get(f"/api/v1/prompts/{pid}", headers=auth_headers)
        assert one.status_code == 200 and one.json()["name"] == "Listable"


class TestVersioning:
    async def test_create_version_increments(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "Versioned", "initial_content": "v1"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.post(
            f"/api/v1/prompts/{prompt['id']}/versions",
            json={"content": "v2 content", "commit_message": "second cut"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["version"] == 2

    async def test_list_versions(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "Many Versions", "initial_content": "v1"},
                headers=auth_headers,
            )
        ).json()
        await client.post(
            f"/api/v1/prompts/{prompt['id']}/versions", json={"content": "v2"}, headers=auth_headers
        )
        listing = await client.get(f"/api/v1/prompts/{prompt['id']}/versions", headers=auth_headers)
        assert listing.status_code == 200
        versions = [v["version"] for v in listing.json()]
        assert versions == [2, 1]

    async def test_get_specific_version(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "Get Ver", "initial_content": "v1"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.get(f"/api/v1/prompts/{prompt['id']}/versions/1", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "v1"

    async def test_missing_version_404(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "No Ver", "initial_content": "v1"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.get(f"/api/v1/prompts/{prompt['id']}/versions/99", headers=auth_headers)
        assert resp.status_code == 404


class TestRendering:
    async def test_render_current_version(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "Render", "initial_content": "Hello {{name}}, you are a {{role}}."},
                headers=auth_headers,
            )
        ).json()
        resp = await client.post(
            f"/api/v1/prompts/{prompt['id']}/render",
            json={"name": "Ada", "role": "scientist"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Hello Ada, you are a scientist."

    async def test_render_specific_version(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "Render V", "initial_content": "v1 {{x}}"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.post(
            f"/api/v1/prompts/{prompt['id']}/render",
            json={"x": "value"},
            params={"version": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "v1 value"

    async def test_render_missing_version_404(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "Render Miss", "initial_content": "x"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.post(
            f"/api/v1/prompts/{prompt['id']}/render",
            json={},
            params={"version": 42},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestRollback:
    async def test_rollback_creates_new_version(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "Rollback", "initial_content": "original"},
                headers=auth_headers,
            )
        ).json()
        await client.post(
            f"/api/v1/prompts/{prompt['id']}/versions",
            json={"content": "changed content"},
            headers=auth_headers,
        )
        resp = await client.post(
            f"/api/v1/prompts/{prompt['id']}/rollback/1", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 3
        assert resp.json()["content"] == "original"
        # Current version now points at the rollback
        render = await client.post(
            f"/api/v1/prompts/{prompt['id']}/render", json={}, headers=auth_headers
        )
        assert render.json()["content"] == "original"

    async def test_rollback_missing_version_404(self, client, auth_headers, test_workspace):
        prompt = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/prompts",
                json={"name": "No Rollback", "initial_content": "x"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.post(
            f"/api/v1/prompts/{prompt['id']}/rollback/99", headers=auth_headers
        )
        assert resp.status_code == 404


class TestPublicPrompts:
    async def test_public_prompt_listing(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/prompts",
            json={"name": "Public Prompt", "is_public": True, "initial_content": "x"},
            headers=auth_headers,
        )
        resp = await client.get("/api/v1/prompts/public", headers=auth_headers)
        assert resp.status_code == 200
        assert "Public Prompt" in [p["name"] for p in resp.json()]
