"""Workspace RBAC integration tests.

Covers multi-tenant isolation, role hierarchy enforcement
(Owner > Admin > Member > Viewer), and membership management rules.
"""

import uuid

import pytest


class TestWorkspaceCreation:
    async def test_create_workspace_sets_owner_member(self, client, auth_headers):
        resp = await client.post(
            "/api/v1/workspaces/",
            json={"name": "Rbac Workspace", "description": "desc"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Rbac Workspace"
        assert data["slug"] == "rbac-workspace"
        assert data["member_count"] == 1

    async def test_duplicate_name_gets_unique_slug(self, client, auth_headers):
        r1 = await client.post("/api/v1/workspaces/", json={"name": "Same Name"}, headers=auth_headers)
        r2 = await client.post("/api/v1/workspaces/", json={"name": "Same Name"}, headers=auth_headers)
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["slug"] == "same-name"
        assert r2.json()["slug"] == "same-name-1"

    async def test_create_workspace_requires_auth(self, client):
        resp = await client.post("/api/v1/workspaces/", json={"name": "No Auth"})
        assert resp.status_code == 401


class TestAccessControl:
    async def test_non_member_cannot_read_workspace(self, client, second_user, test_workspace):
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403

    async def test_non_member_cannot_update_workspace(self, client, second_user, test_workspace):
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}",
            json={"name": "hacked"},
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403

    async def test_non_member_cannot_delete_workspace(self, client, second_user, test_workspace):
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403

    async def test_member_listing_is_scoped_to_user(self, client, auth_headers, test_workspace):
        resp = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert resp.status_code == 200
        ids = [ws["id"] for ws in resp.json()]
        assert test_workspace["id"] in ids

    async def test_second_user_does_not_see_workspace(self, client, second_user, test_workspace):
        resp = await client.get("/api/v1/workspaces/", headers=second_user["auth_headers"])
        assert resp.status_code == 200
        assert test_workspace["id"] not in [ws["id"] for ws in resp.json()]


class TestMembershipManagement:
    async def test_owner_can_add_member(self, client, auth_headers, second_user, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "viewer"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "viewer"
        assert data["user_id"] == second_user["id"]
        assert data["email"] == second_user["email"]

    async def test_add_duplicate_member_conflicts(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "viewer"},
            headers=auth_headers,
        )
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_add_nonexistent_user_404(self, client, auth_headers, test_workspace):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": str(uuid.uuid4()), "role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_member_role_can_be_promoted(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "viewer"},
            headers=auth_headers,
        )
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/members/{second_user['id']}",
            json={"role": "admin"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    async def test_owner_role_cannot_be_changed(self, client, auth_headers, test_workspace):
        me = await client.get("/api/v1/auth/me", headers=auth_headers)
        owner_id = me.json()["id"]
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/members/{owner_id}",
            json={"role": "member"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_owner_cannot_be_removed(self, client, auth_headers, test_workspace):
        me = await client.get("/api/v1/auth/me", headers=auth_headers)
        owner_id = me.json()["id"]
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/members/{owner_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_remove_nonexistent_member_404(self, client, auth_headers, test_workspace):
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/members/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_member_can_be_removed(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "member"},
            headers=auth_headers,
        )
        resp = await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/members/{second_user['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_added_member_can_access_workspace(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "viewer"},
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 200

    async def test_removed_member_loses_access(self, client, auth_headers, second_user, test_workspace):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "viewer"},
            headers=auth_headers,
        )
        await client.delete(
            f"/api/v1/workspaces/{test_workspace['id']}/members/{second_user['id']}",
            headers=auth_headers,
        )
        resp = await client.get(
            f"/api/v1/workspaces/{test_workspace['id']}",
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403
