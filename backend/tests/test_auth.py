"""Integration tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


class TestAuthRegister:
    async def test_register_success(self, client: AsyncClient):
        """Should register a new user and return tokens."""
        response = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "full_name": "New User",
            "password": "password123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"
        assert "id" in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user_data: dict):
        """Should reject duplicate email registration."""
        await client.post("/api/v1/auth/register", json=test_user_data)
        response = await client.post("/api/v1/auth/register", json=test_user_data)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_register_invalid_email(self, client: AsyncClient):
        """Should reject invalid email format."""
        response = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "username": "validuser",
            "full_name": "Valid User",
            "password": "password123",
        })
        assert response.status_code == 422

    async def test_register_weak_password(self, client: AsyncClient):
        """Should reject too-short passwords."""
        response = await client.post("/api/v1/auth/register", json={
            "email": "weak@example.com",
            "username": "weakuser",
            "full_name": "Weak User",
            "password": "ab",
        })
        assert response.status_code == 422


class TestAuthLogin:
    async def test_login_success(self, client: AsyncClient, test_user_data: dict):
        """Should authenticate and return JWT tokens."""
        await client.post("/api/v1/auth/register", json=test_user_data)
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user_data: dict):
        """Should reject wrong password."""
        await client.post("/api/v1/auth/register", json=test_user_data)
        response = await client.post("/api/v1/auth/login", json={
            "email": test_user_data["email"],
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Should reject login for unregistered email."""
        response = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "password123",
        })
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
        response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401


class TestAuthRefresh:
    async def test_refresh_success(self, client: AsyncClient, test_user: dict):
        """Should refresh an access token."""
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": test_user["refresh_token"],
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_refresh_invalid(self, client: AsyncClient):
        """Should reject invalid refresh token."""
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_refresh_token",
        })
        assert response.status_code == 401


class TestAuthLogout:
    async def test_logout_success(self, client: AsyncClient, test_user: dict):
        """Should return 204 on logout."""
        headers = {"Authorization": f"Bearer {test_user['access_token']}"}
        response = await client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 204
