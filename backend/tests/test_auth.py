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


class TestAuthLogout:
    async def test_logout_success(self, client: AsyncClient, test_user: dict):
        """Should return 204 on logout."""
        headers = {"Authorization": f"Bearer {test_user['access_token']}"}
        response = await client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 204
