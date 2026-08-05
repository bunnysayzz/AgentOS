"""Workspace member-management tests.

Covers the two real bugs found in the Add Member flow:
- role values were sent UPPERCASE by the UI while the enum stores lowercase,
  so every add/update 422'd silently;
- the Add Member form only accepted raw UUIDs (now it can resolve emails via
  GET /users/lookup).
"""

import pytest
from httpx import AsyncClient


class TestRoleCaseInsensitivity:
    async def test_schema_accepts_uppercase_role(self):
        """The UI sends 'MEMBER'/'ADMIN'; the schema must normalize to lowercase."""
        from app.models.workspace import MembershipRole
        from app.schemas.workspace import WorkspaceMemberAdd, WorkspaceMemberUpdate

        add = WorkspaceMemberAdd(user_id="ed0dffdf-bf32-4655-bf95-7caacb9b6383", role="MEMBER")
        assert add.role is MembershipRole.MEMBER

        upd = WorkspaceMemberUpdate(role="ADMIN")
        assert upd.role is MembershipRole.ADMIN


class TestAddMember:
    async def test_add_member_with_uppercase_role(self, client: AsyncClient, test_workspace: dict, second_user: dict, auth_headers: dict):
        """Adding a member with role='MEMBER' (what the UI sends) returns 201."""
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "MEMBER"},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["user_id"] == second_user["id"]
        assert data["role"] == "member"
        assert data["email"] == "other@example.com"

    async def test_add_member_with_lowercase_role(self, client: AsyncClient, test_workspace: dict, second_user: dict, auth_headers: dict):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "admin"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "admin"

    async def test_add_unknown_user_404(self, client: AsyncClient, test_workspace: dict, auth_headers: dict):
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": "ffffffff-0000-4000-8000-000000000000", "role": "viewer"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert "User not found" in resp.json()["detail"]

    async def test_add_duplicate_member_409(self, client: AsyncClient, test_workspace: dict, second_user: dict, auth_headers: dict):
        first = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "member"},
            headers=auth_headers,
        )
        assert first.status_code == 201

        second = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "member"},
            headers=auth_headers,
        )
        assert second.status_code == 409
        assert "already a member" in second.json()["detail"]

    async def test_non_member_cannot_add(self, client: AsyncClient, test_workspace: dict, second_user: dict):
        """A user who isn't in the workspace can't add members (403)."""
        resp = await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "member"},
            headers=second_user["auth_headers"],
        )
        assert resp.status_code == 403


class TestUpdateMemberRole:
    async def test_update_role_accepts_uppercase(self, client: AsyncClient, test_workspace: dict, second_user: dict, auth_headers: dict):
        await client.post(
            f"/api/v1/workspaces/{test_workspace['id']}/members",
            json={"user_id": second_user["id"], "role": "member"},
            headers=auth_headers,
        )
        resp = await client.patch(
            f"/api/v1/workspaces/{test_workspace['id']}/members/{second_user['id']}",
            json={"role": "ADMIN"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


class TestUserLookup:
    async def test_lookup_by_email(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/users/lookup", params={"email": "test@example.com"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert "id" in data

    async def test_lookup_case_insensitive(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/users/lookup", params={"email": "TEST@Example.COM"}, headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    async def test_lookup_unknown_email_404(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/users/lookup", params={"email": "nobody@example.com"}, headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_lookup_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/lookup", params={"email": "test@example.com"})
        assert resp.status_code == 401


class TestWorkspaceRoleInResponse:
    async def test_workspace_response_includes_current_role(self, client: AsyncClient, test_workspace: dict, auth_headers: dict):
        """The UI chip showed 'member' for everyone — the response now carries the real role."""
        resp = await client.get(f"/api/v1/workspaces/{test_workspace['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["role"] == "owner"

    async def test_list_workspaces_includes_role(self, client: AsyncClient, test_workspace: dict, auth_headers: dict):
        resp = await client.get("/api/v1/workspaces/", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert any(w["id"] == test_workspace["id"] and w["role"] == "owner" for w in items)
