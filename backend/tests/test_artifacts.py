"""Artifact Store integration tests: registration, listing, filtering, lifecycle."""


class TestArtifactCRUD:
    async def test_create_artifact(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            json={"name": "config.json", "content_type": "application/json"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "config.json"
        assert data["version"] == 1
        assert data["size_bytes"] == 0

    async def test_list_and_filter_by_content_type(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            json={"name": "a.json", "content_type": "application/json"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            json={"name": "b.txt", "content_type": "text/plain"},
            headers=auth_headers,
        )
        all_resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/", headers=auth_headers
        )
        assert len(all_resp.json()) == 2

        filtered = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
            params={"content_type": "text/plain"},
            headers=auth_headers,
        )
        assert len(filtered.json()) == 1
        assert filtered.json()[0]["name"] == "b.txt"

    async def test_get_artifact(self, client, auth_headers, test_workspace):
        artifact = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
                json={"name": "spec.md", "content_type": "text/markdown"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/{artifact['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "spec.md"

    async def test_update_metadata(self, client, auth_headers, test_workspace):
        artifact = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
                json={"name": "old-name.json", "content_type": "application/json"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/{artifact['id']}",
            json={"name": "new-name.json", "metadata": {"env": "prod"}},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "new-name.json"
        assert data["artifact_metadata"] == {"env": "prod"}

    async def test_delete_artifact(self, client, auth_headers, test_workspace):
        artifact = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
                json={"name": "old.log", "content_type": "text/plain"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/{artifact['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 204
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/artifacts/", headers=auth_headers
        )
        assert artifact["id"] not in [a["id"] for a in listing.json()]

    async def test_artifact_isolated_per_workspace(self, client, auth_headers, second_user, test_workspace):
        artifact = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/artifacts/",
                json={"name": "private.txt", "content_type": "text/plain"},
                headers=auth_headers,
            )
        ).json()
        other_ws = (
            await client.post("/api/v1/workspaces/", json={"name": "Other"}, headers=second_user["auth_headers"])
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{other_ws['id']}/artifacts/{artifact['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 404
