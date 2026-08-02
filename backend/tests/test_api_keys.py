"""API Key integration tests: creation, hashed storage, header auth, revocation."""

import uuid


class TestApiKeyCreation:
    async def test_create_returns_full_key_once(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/api-keys/", json={"name": "My CLI Key"}, headers=auth_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["full_key"].startswith("agos_")
        assert data["key_prefix"].startswith("agos_")
        assert data["is_active"] is True

    async def test_list_never_returns_full_key(self, client, auth_headers):
        await client.post("/api/v1/api-keys/", json={"name": "Key A"}, headers=auth_headers)
        await client.post("/api/v1/api-keys/", json={"name": "Key B"}, headers=auth_headers)
        resp = await client.get("/api/v1/api-keys/", headers=auth_headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 2
        for key in keys:
            assert "full_key" not in key
            assert key["name"] in ("Key A", "Key B")


class TestApiKeyAuth:
    async def test_authenticate_with_api_key_header(self, client, auth_headers):
        created = (
            await client.post("/api/v1/api-keys/", json={"name": "Auth Key"}, headers=auth_headers)
        ).json()
        full_key = created["full_key"]

        resp = await client.get("/api/v1/auth/me", headers={"X-API-Key": full_key})
        assert resp.status_code == 200
        assert resp.json()["email"]  # authenticated as the key's owner

    async def test_invalid_api_key_rejected(self, client):
        resp = await client.get("/api/v1/auth/me", headers={"X-API-Key": "agos_xxxx_invalid"})
        assert resp.status_code == 401

    async def test_missing_credentials_rejected(self, client):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_api_key_scoped_to_user(self, client, auth_headers, second_user):
        created = (
            await client.post("/api/v1/api-keys/", json={"name": "My Key"}, headers=auth_headers)
        ).json()
        # The second user cannot list the first user's keys
        resp = await client.get("/api/v1/api-keys/", headers=second_user["auth_headers"])
        assert resp.status_code == 200
        assert created["id"] not in [k["id"] for k in resp.json()]


class TestApiKeyRevocation:
    async def test_revoke_key(self, client, auth_headers):
        created = (
            await client.post("/api/v1/api-keys/", json={"name": "Revokable"}, headers=auth_headers)
        ).json()
        resp = await client.delete(f"/api/v1/api-keys/{created['id']}", headers=auth_headers)
        assert resp.status_code == 204

        # Key no longer authenticates
        me = await client.get("/api/v1/auth/me", headers={"X-API-Key": created["full_key"]})
        assert me.status_code == 401

    async def test_revoke_nonexistent_key_404(self, client, auth_headers):
        resp = await client.delete(
            f"/api/v1/api-keys/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_cannot_revoke_others_key(self, client, auth_headers, second_user):
        created = (
            await client.post("/api/v1/api-keys/", json={"name": "Mine"}, headers=auth_headers)
        ).json()
        resp = await client.delete(
            f"/api/v1/api-keys/{created['id']}", headers=second_user["auth_headers"]
        )
        assert resp.status_code == 404
