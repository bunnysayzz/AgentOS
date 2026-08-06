"""Tests for account lifecycle: GDPR data export + right-to-be-forgotten."""

import uuid

import pytest
from httpx import AsyncClient

from app.core.db import FirestoreDB
from app.core.database import get_db
from app.services import workspace_service


def _get_db() -> FirestoreDB:
    """Reach the current dependency-overridden DB (the fake Firestore)."""
    for dep, factory in app_dependency_overrides():
        if dep is get_db:
            gen = factory()
            return next(gen)
    raise RuntimeError("get_db override not found")


def app_dependency_overrides():
    from app.main import app
    return list(app.dependency_overrides.items())


async def test_export_includes_workspace_and_child_data(
    client: AsyncClient, auth_headers: dict, test_workspace: dict
):
    """Export should include the profile, owned workspace, and its children."""
    # Add an agent + secret so the snapshot has real children.
    await client.post(
        f"/api/v1/workspaces/{test_workspace['id']}/agents/",
        json={"name": "Export Agent", "model_name": "gpt-4o"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/v1/workspaces/{test_workspace['id']}/secrets/",
        json={"name": "Key", "slug": "key", "value": "sk-super-secret"},
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/users/me/export", headers=auth_headers)
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    data = resp.json()

    assert data["schema_version"] == "1.0"
    assert data["user"]["email"] == "test@example.com"
    assert len(data["workspaces"]) == 1

    ws = data["workspaces"][0]
    assert ws["workspace"]["name"] == "Test Workspace"
    agents = ws["collections"].get("agents", [])
    assert len(agents) == 1
    assert agents[0]["name"] == "Export Agent"

    # Secrets export must include the DECRYPTED value (the user's own data).
    secrets = ws["collections"].get("secrets", [])
    assert len(secrets) == 1
    assert secrets[0]["value"] == "sk-super-secret"
    assert "encrypted_value" not in secrets[0]


async def test_export_does_not_include_other_users_workspaces(
    client: AsyncClient, auth_headers: dict, second_user: dict, test_workspace: dict
):
    """A member-only workspace is exported only as a membership reference."""
    # Add the second user to the workspace as a member.
    db = _get_db()
    workspace = await workspace_service.get_workspace_by_id(db, test_workspace["id"])
    from app.schemas.workspace import WorkspaceMemberAdd
    await workspace_service.add_member(db, workspace, WorkspaceMemberAdd(
        user_id=uuid.UUID(second_user["id"]), role="member"
    ))

    resp = await client.get("/api/v1/users/me/export", headers=second_user["auth_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["workspaces"]) == 1
    # Member-only: no collections, just a membership record.
    ws = data["workspaces"][0]
    assert "membership" in ws
    assert ws["membership"]["user_id"] == second_user["id"]
    assert "collections" not in ws


async def test_delete_account_removes_owned_workspace_and_contents(
    client: AsyncClient, auth_headers: dict, test_workspace: dict
):
    """Deleting the account purges owned workspaces, children, and API keys."""
    # Create an agent + an API key first.
    await client.post(
        f"/api/v1/workspaces/{test_workspace['id']}/agents/",
        json={"name": "Doomed Agent", "model_name": "gpt-4o"},
        headers=auth_headers,
    )
    key_resp = await client.post(
        "/api/v1/api-keys/", json={"name": "CI Key"}, headers=auth_headers
    )
    assert key_resp.status_code == 201

    resp = await client.delete("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 204

    db = _get_db()
    # Workspace gone entirely (hard delete).
    assert db.get("workspaces", test_workspace["id"]) is None
    # Its agents + memberships gone.
    assert db.query("agents", "workspace_id", test_workspace["id"]) == []
    assert db.query("workspace_members", "workspace_id", test_workspace["id"]) == []
    # API key gone.
    assert db.query("api_keys") == []
    # User soft-deleted (deleted_at set, is_active False).
    user_doc = db.get("users", _find_test_user_id(db))
    assert user_doc is not None
    assert user_doc.get("deleted_at")
    assert user_doc.get("is_active") is False


async def test_delete_account_keeps_shared_workspace_intact(
    client: AsyncClient, auth_headers: dict, second_user: dict, test_workspace: dict
):
    """Deleting a member-only account leaves the workspace and other members."""
    db = _get_db()
    workspace = await workspace_service.get_workspace_by_id(db, test_workspace["id"])
    from app.schemas.workspace import WorkspaceMemberAdd
    await workspace_service.add_member(db, workspace, WorkspaceMemberAdd(
        user_id=uuid.UUID(second_user["id"]), role="member"
    ))

    # Second user deletes their account.
    resp = await client.delete("/api/v1/users/me", headers=second_user["auth_headers"])
    assert resp.status_code == 204

    # Workspace survives; only the second user's membership row is gone.
    assert db.get("workspaces", test_workspace["id"]) is not None
    members = db.query("workspace_members", "workspace_id", test_workspace["id"])
    assert len(members) == 1
    assert members[0]["user_id"] == _find_test_user_id(db)
    assert all(m["user_id"] != second_user["id"] for m in members)


async def test_delete_account_requires_auth(client: AsyncClient):
    """Unauthenticated deletion must be rejected."""
    resp = await client.delete("/api/v1/users/me")
    assert resp.status_code == 401


# ─── Helpers ─────────────────────────────────────────


def _find_test_user_id(db: FirestoreDB) -> str | None:
    for row in db.query("users"):
        if row.get("email") == "test@example.com":
            return row["id"]
    return None
