"""Secrets Manager integration tests: encryption at rest, value non-leakage, lifecycle."""

from uuid import UUID

from app.services import secret_service
from app.models.secret import SecretProvider


class TestSecretSecurity:
    async def test_create_secret_never_returns_value(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            json={"name": "OPENAI_KEY", "slug": "openai_key", "value": "sk-super-secret-123"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "value" not in data
        assert "encrypted_value" not in data
        assert data["name"] == "OPENAI_KEY"

    async def test_list_secrets_never_leaks_values(self, client, auth_headers, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            json={"name": "A", "slug": "a", "value": "secret-a"},
            headers=auth_headers,
        )
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            json={"name": "B", "slug": "b", "value": "secret-b"},
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/", headers=auth_headers
        )
        assert resp.status_code == 200
        for secret in resp.json():
            assert "value" not in secret
            assert "encrypted_value" not in secret
            assert "secret-a" not in str(secret)
            assert "secret-b" not in str(secret)

    async def test_value_is_encrypted_at_rest(self, client, auth_headers, test_workspace, db_session):
        created = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
            json={"name": "Enc", "slug": "enc", "value": "plaintext-value-xyz"},
            headers=auth_headers,
        )
        secret = await secret_service.get_secret_by_id(db_session, UUID(created.json()["id"]))
        assert secret is not None
        assert secret.encrypted_value != "plaintext-value-xyz"
        assert "plaintext-value-xyz" not in secret.encrypted_value
        # Decryptable back to the original
        assert secret_service.decrypt_value(secret.encrypted_value) == "plaintext-value-xyz"


class TestSecretLifecycle:
    async def test_get_secret(self, client, auth_headers, test_workspace):
        secret = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
                json={"name": "Get", "slug": "get", "value": "v"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/{secret['id']}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get"

    async def test_update_value_reencrypts(self, client, auth_headers, test_workspace, db_session):
        secret = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
                json={"name": "Upd", "slug": "upd", "value": "old-value"},
                headers=auth_headers,
            )
        ).json()
        old = await secret_service.get_secret_by_id(db_session, UUID(secret["id"]))
        old_cipher = old.encrypted_value

        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/{secret['id']}",
            json={"value": "new-value"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        updated = await secret_service.get_secret_by_id(db_session, UUID(secret["id"]))
        assert updated.encrypted_value != old_cipher
        assert secret_service.decrypt_value(updated.encrypted_value) == "new-value"

    async def test_duplicate_slug_conflict(self, client, auth_headers, test_workspace):
        payload = {"name": "Dup", "slug": "dup", "value": "v"}
        r1 = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/", json=payload, headers=auth_headers
        )
        assert r1.status_code == 201
        r2 = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/", json=payload, headers=auth_headers
        )
        assert r2.status_code == 409

    async def test_delete_secret(self, client, auth_headers, test_workspace):
        secret = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
                json={"name": "Del", "slug": "del", "value": "v"},
                headers=auth_headers,
            )
        ).json()
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/{secret['id']}", headers=auth_headers
        )
        assert resp.status_code == 204
        listing = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}/secrets/", headers=auth_headers
        )
        assert secret["id"] not in [s["id"] for s in listing.json()]

    async def test_cross_workspace_secret_404(self, client, auth_headers, second_user, test_workspace):
        secret = (
            await client.post(
                f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
                json={"name": "Isolated", "slug": "isolated", "value": "v"},
                headers=auth_headers,
            )
        ).json()
        other_ws = (
            await client.post("/api/v1/workspaces/", json={"name": "Other"}, headers=second_user["auth_headers"])
        ).json()
        resp = await client.get(
            f"/api/v1/workspaces/{other_ws['id']}/secrets/{secret['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 404
