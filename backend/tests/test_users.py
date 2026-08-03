"""User domain integration tests: profile, password change, superuser gating."""

import uuid


class TestProfile:
    async def test_get_me(self, client, auth_headers, test_user):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == test_user["email"]
        assert "hashed_password" not in data

    async def test_get_self_by_id(self, client, auth_headers, test_user):
        resp = await client.get(f"/api/v1/users/{test_user['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == test_user["email"]

    async def test_get_other_user_forbidden(self, client, auth_headers, second_user):
        resp = await client.get(f"/api/v1/users/{second_user['id']}", headers=auth_headers)
        assert resp.status_code == 403

    async def test_update_own_profile(self, client, auth_headers, test_user):
        resp = await client.patch(
            f"/api/v1/users/{test_user['id']}",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    async def test_update_other_user_forbidden(self, client, auth_headers, second_user):
        resp = await client.patch(
            f"/api/v1/users/{second_user['id']}",
            json={"full_name": "Hacked"},
            headers=auth_headers,
        )
        assert resp.status_code == 403


class TestPasswordChange:
    async def test_password_change_handled_by_firebase(self, client, auth_headers, test_user):
        """Password changes go through Firebase Auth — the backend endpoint
        intentionally rejects them with a clear message."""
        resp = await client.post(
            "/api/v1/users/password",
            json={"current_password": "testpass123", "new_password": "brandnewpass1"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Firebase" in resp.json()["detail"]

    async def test_weak_new_password_rejected(self, client, auth_headers, test_user):
        resp = await client.post(
            "/api/v1/users/password",
            json={"current_password": "testpass123", "new_password": "short"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestSuperuserGates:
    async def test_list_users_requires_superuser(self, client, auth_headers):
        resp = await client.get("/api/v1/users/", headers=auth_headers)
        assert resp.status_code == 403

    async def test_delete_user_requires_superuser(self, client, auth_headers, second_user):
        resp = await client.delete(f"/api/v1/users/{second_user['id']}", headers=auth_headers)
        assert resp.status_code == 403
