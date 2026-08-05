"""Integration tests for Firebase-first authentication.

Tokens use the fake format ``firebase.<email>[:<name>]`` — the conftest
monkeypatches token verification, so no real Firebase is required.
"""

import pytest
from httpx import AsyncClient


class TestFirebaseAuth:
    async def test_me_auto_creates_user(self, client: AsyncClient):
        """First authenticated request should auto-register the user."""
        token = "firebase.newuser@example.com:New User"
        response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "id" in data

    async def test_firebase_exchange_endpoint(self, client: AsyncClient):
        """POST /auth/firebase exchanges an ID token for a user profile."""
        token = "firebase.exchange@example.com"
        response = await client.post("/api/v1/auth/firebase", json={"id_token": token})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "exchange@example.com"

    async def test_same_email_returns_same_user(self, client: AsyncClient):
        """Repeated authentication with the same email is idempotent."""
        token = "firebase.same@example.com"
        r1 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        r2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["id"] == r2.json()["id"]

    async def test_email_signup_starts_unverified(self, client: AsyncClient):
        """Email/password signups stay unverified until the link is clicked."""
        token = "firebase.unverified@example.com"
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "unverified@example.com"
        assert data["is_verified"] is False

    async def test_email_verified_claim_reflected(self, client: AsyncClient):
        """A token carrying email_verified=True keeps the account verified."""
        token = "firebase.verified@example.com:V User~https://example.com/p.png"
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "verified@example.com"
        assert data["is_verified"] is True

    async def test_login_does_not_overwrite_verification_with_true(self, client: AsyncClient, db_session):
        """A second login with an unverified token must NOT re-verify the user.

        This pins the fix for the old hardcoded ``updates["is_verified"] = True``:
        an account that verifies then unverifies (email change) or never
        verifies must keep the token's real state.
        """
        from app.core.db import now_iso

        # Pre-existing user marked verified in the past.
        user_id = "cccccccc-dddd-4eee-8fff-000000000000"
        db_session.set("users", user_id, {
            "id": user_id,
            "email": "flip@example.com",
            "username": "flip",
            "full_name": "Flip",
            "avatar_url": None,
            "is_active": True,
            "is_superuser": False,
            "is_verified": True,
            "last_login_at": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

        token = "firebase.flip@example.com"
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_verified"] is False

    async def test_invalid_token(self, client: AsyncClient):
        """Should reject an invalid token."""
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-firebase-token"}
        )
        assert response.status_code == 401

    async def test_no_token(self, client: AsyncClient):
        """Should reject unauthenticated request."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestAuthMe:
    async def test_me_success(self, client: AsyncClient, test_user: dict):
        """Should return authenticated user profile."""
        headers = {"Authorization": f"Bearer {test_user['access_token']}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == test_user["email"]

    async def test_me_no_token(self, client: AsyncClient):
        """Should reject unauthenticated request."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient):
        """Should reject invalid token."""
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 401


class TestUsers:
    async def test_get_user_by_id(self, client: AsyncClient, test_user: dict):
        """Should fetch a user by ID."""
        headers = {"Authorization": f"Bearer {test_user['access_token']}"}
        response = await client.get(f"/api/v1/users/{test_user['id']}", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == test_user["email"]

    async def test_update_profile(self, client: AsyncClient, test_user: dict):
        """Should update the user's own profile."""
        headers = {"Authorization": f"Bearer {test_user['access_token']}"}
        response = await client.patch(
            f"/api/v1/users/{test_user['id']}",
            json={"full_name": "Renamed User"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Renamed User"


class TestLegacyUserDocs:
    """Pre-Firestore-migration user docs held None/"None" where the API
    expects real bools/strings — /users/me used to 500. These tests pin the
    normalization that keeps those accounts healthy."""

    async def test_legacy_doc_with_none_bools_does_not_500(self, client: AsyncClient, db_session):
        """A legacy doc with is_superuser=None and avatar_url='None' still returns 200."""
        from app.core.db import now_iso

        user_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        db_session.set("users", user_id, {
            "id": user_id,
            "email": "legacy@example.com",
            "username": "legacy",
            "full_name": None,
            "avatar_url": "None",  # literal string from the old DB
            "is_active": True,
            "is_superuser": None,   # missing key → None
            "is_verified": None,
            # last_login_at / updated_at keys entirely absent (old docs)
            "created_at": now_iso(),
        })

        token = "firebase.legacy@example.com"
        response = await client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "legacy@example.com"
        assert data["is_superuser"] is False
        assert data["is_active"] is True
        assert data["avatar_url"] is None

    async def test_google_login_populates_avatar_from_claims(self, client: AsyncClient, db_session):
        """A Google login with name/picture claims fills in missing profile fields.

        Token name suffix ``~<url>`` carries the Google ``picture`` claim (see
        conftest's fake verifier).
        """
        from app.core.db import now_iso

        user_id = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"
        db_session.set("users", user_id, {
            "id": user_id,
            "email": "google@example.com",
            "username": "google",
            "full_name": None,
            "avatar_url": "None",  # legacy placeholder
            "is_active": True,
            "is_superuser": False,
            "is_verified": False,
            "last_login_at": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

        token = "firebase.google@example.com:Google User~https://example.com/me.jpg"
        response = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Google User"
        assert data["is_verified"] is True
        # The Google photo claim replaces the legacy 'None' placeholder.
        assert data["avatar_url"] == "https://example.com/me.jpg"


class TestAuthLogout:
    async def test_logout_success(self, client: AsyncClient, test_user: dict):
        """Should return 204 on logout."""
        headers = {"Authorization": f"Bearer {test_user['access_token']}"}
        response = await client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 204
