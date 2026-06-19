"""Integration tests for admin auth endpoints."""

import pytest


class TestAdminLogin:
    async def test_login_success_admin(self, client):
        """Admin user with correct password receives JWT and permissions."""
        r = await client.post("/api/admin/auth/login", json={
            "username": "admin", "password": "1234"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "access_token" in data
        assert data["user"]["name"] == "Admin"
        assert data["user"]["role"] == "ADMIN"
        assert data["expires_in"] == 14400  # 4h for admin

    async def test_login_wrong_password(self, client):
        """Wrong password returns 401."""
        r = await client.post("/api/admin/auth/login", json={
            "username": "admin", "password": "wrongpass"
        })
        assert r.status_code == 401, r.text

    async def test_login_dispatcher_rejected(self, client):
        """DISPATCHER role cannot log into admin, even with correct credentials."""
        r = await client.post("/api/admin/auth/login", json={
            "username": "carlos", "password": "1234"
        })
        assert r.status_code == 403, r.text
        data = r.json()
        assert "Acceso restringido" in data.get("detail", "")

    async def test_login_nonexistent_user(self, client):
        """Non-existent user returns 401."""
        r = await client.post("/api/admin/auth/login", json={
            "username": "ghost", "password": "12345678"
        })
        assert r.status_code == 401

    async def test_login_missing_fields(self, client):
        """Missing password returns 422."""
        r = await client.post("/api/admin/auth/login", json={
            "username": "admin"
        })
        assert r.status_code == 422

    async def test_login_missing_username(self, client):
        """Missing username returns 422."""
        r = await client.post("/api/admin/auth/login", json={
            "password": "12345678"
        })
        assert r.status_code == 422


class TestAdminAuthBackwardCompat:
    """POS login must keep working exactly as before."""

    async def test_pos_login_still_works(self, client):
        """POS dispatcher login unchanged."""
        r = await client.post("/api/pos/auth/login", json={
            "username": "carlos", "pin": "1234"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["role"] == "DISPATCHER"
        assert data["expires_in"] == 28800  # 8h for POS

    async def test_pos_login_admin_user(self, client):
        """Admin user can also log into POS (for testing/diagnostics)."""
        r = await client.post("/api/pos/auth/login", json={
            "username": "admin", "pin": "1234"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["role"] == "ADMIN"
        assert data["expires_in"] == 28800  # POS duration


class TestAdminAuthRequired:
    """Admin endpoints reject unauthorized access."""

    def _admin_token(self, db):
        """Build a valid admin JWT for testing."""
        from app.services.auth_service import create_access_token
        return create_access_token(1, "admin", expire_minutes=240)

    def _dispatcher_token(self, db):
        """Build a valid dispatcher JWT for testing."""
        from app.services.auth_service import create_access_token
        return create_access_token(2, "carlos")

    async def test_no_token_returns_401(self, client):
        """Admin endpoint without token returns 401."""
        r = await client.get("/api/pos/products")  # any protected endpoint
        assert r.status_code == 401


class TestAdminDeps:
    """Unit-style tests for admin dependencies."""

    async def test_admin_user_has_permissions(self, client):
        """Admin login response includes permissions from role."""
        r = await client.post("/api/admin/auth/login", json={
            "username": "admin", "password": "1234"
        })
        assert r.status_code == 200
        data = r.json()
        # Role ADMIN has no permissions_json in seed data (empty dict)
        assert "permissions" in data["user"]
