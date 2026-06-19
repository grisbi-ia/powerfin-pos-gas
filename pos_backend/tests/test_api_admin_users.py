"""Integration tests for admin users CRUD endpoints."""

import pytest


# ── Helpers ────────────────────────────────────────────────────────


def _admin_headers():
    """Build auth headers for the admin user (user_id=1, role=ADMIN)."""
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    """Build auth headers for carlos (user_id=2, role=DISPATCHER)."""
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


# ── List users ─────────────────────────────────────────────────────


class TestListUsers:
    async def test_list_all_users(self, client):
        """Admin can list all users with pagination."""
        r = await client.get("/api/admin/users", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2  # admin + carlos from seed
        assert data["page"] == 1
        assert "items" in data
        assert len(data["items"]) > 0

    async def test_list_pagination(self, client):
        """Pagination params are respected."""
        r = await client.get(
            "/api/admin/users?page=1&page_size=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert data["page_size"] == 1

    async def test_list_search_by_name(self, client):
        """Search filters by name."""
        r = await client.get(
            "/api/admin/users?search=carlos", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["username"] == "carlos"

    async def test_list_search_by_username(self, client):
        """Search filters by username."""
        r = await client.get(
            "/api/admin/users?search=admin", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        usernames = [u["username"] for u in data["items"]]
        assert "admin" in usernames

    async def test_list_filter_by_role(self, client):
        """Role filter returns only users with that role."""
        r = await client.get(
            "/api/admin/users?role=DISPATCHER", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert item["role"] == "DISPATCHER"

    async def test_list_sort_desc(self, client):
        """Sort order desc works."""
        r = await client.get(
            "/api/admin/users?sort=name&order=desc", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        names = [u["name"] for u in data["items"]]
        assert names == sorted(names, reverse=True)

    async def test_list_dispatcher_forbidden(self, client):
        """DISPATCHER cannot access admin users list."""
        r = await client.get("/api/admin/users", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Create user ─────────────────────────────────────────────────────


class TestCreateUser:
    async def test_create_user_success(self, client):
        """Admin can create a new user."""
        r = await client.post("/api/admin/users", json={
            "username": "nuevo",
            "name": "Usuario Nuevo",
            "password": "password123",
            "role_id": 2,  # DISPATCHER
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["username"] == "nuevo"
        assert data["name"] == "Usuario Nuevo"
        assert data["role"] == "DISPATCHER"
        assert data["is_active"] is True
        assert "pin_hash" not in data  # never expose hash

    async def test_create_user_duplicate_username(self, client):
        """Duplicate username returns 409."""
        r = await client.post("/api/admin/users", json={
            "username": "carlos",  # already exists
            "name": "Otro Carlos",
            "password": "password123",
            "role_id": 2,
        }, headers=_admin_headers())
        assert r.status_code == 409

    async def test_create_user_invalid_role(self, client):
        """Non-existent role_id returns 400."""
        r = await client.post("/api/admin/users", json={
            "username": "test2",
            "name": "Test User",
            "password": "password123",
            "role_id": 999,
        }, headers=_admin_headers())
        assert r.status_code == 400

    async def test_create_user_short_password(self, client):
        """Password shorter than 4 chars returns 422."""
        r = await client.post("/api/admin/users", json={
            "username": "test3",
            "name": "Test",
            "password": "ab",
            "role_id": 2,
        }, headers=_admin_headers())
        assert r.status_code == 422

    async def test_create_user_missing_required(self, client):
        """Missing required fields returns 422."""
        r = await client.post("/api/admin/users", json={
            "username": "incompleto"
        }, headers=_admin_headers())
        assert r.status_code == 422

    async def test_created_user_can_login(self, client):
        """Created user can log into the admin panel (if role permits)."""
        # Create an admin user
        r = await client.post("/api/admin/users", json={
            "username": "admin2",
            "name": "Admin Dos",
            "password": "Str0ng!Pass",
            "role_id": 1,  # ADMIN
        }, headers=_admin_headers())
        assert r.status_code == 201

        # Login with the new credentials
        r = await client.post("/api/admin/auth/login", json={
            "username": "admin2",
            "password": "Str0ng!Pass",
        })
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "ADMIN"


# ── Get user ────────────────────────────────────────────────────────


class TestGetUser:
    async def test_get_user_exists(self, client):
        """Admin can get a single user by id."""
        r = await client.get("/api/admin/users/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == 1
        assert data["username"] == "admin"
        assert data["role"] == "ADMIN"

    async def test_get_user_not_found(self, client):
        """Non-existent user returns 404."""
        r = await client.get("/api/admin/users/9999", headers=_admin_headers())
        assert r.status_code == 404


# ── Update user ─────────────────────────────────────────────────────


class TestUpdateUser:
    async def test_update_name(self, client):
        """Update only the name field."""
        r = await client.put("/api/admin/users/2", json={
            "name": "Carlos Actualizado"
        }, headers=_admin_headers())
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Carlos Actualizado"

    async def test_update_password(self, client):
        """Update password and verify new credentials work."""
        # Change password
        r = await client.put("/api/admin/users/2", json={
            "password": "NewPass123"
        }, headers=_admin_headers())
        assert r.status_code == 200

        # Old password should fail (in POS login — user is dispatcher)
        r = await client.post("/api/pos/auth/login", json={
            "username": "carlos", "pin": "1234"
        })
        assert r.status_code == 401  # old pin no longer works

        # New password should work via admin login (but carlos is DISPATCHER → 403)
        r = await client.post("/api/admin/auth/login", json={
            "username": "carlos", "password": "NewPass123"
        })
        assert r.status_code == 403  # role rejected, credentials correct

    async def test_update_role(self, client):
        """Change user role."""
        r = await client.put("/api/admin/users/2", json={
            "role_id": 1  # promote to ADMIN
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["role"] == "ADMIN"
        assert r.json()["role_id"] == 1

    async def test_update_deactivate(self, client):
        """Deactivate a user."""
        r = await client.put("/api/admin/users/2", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_not_found(self, client):
        """Update non-existent user returns 404."""
        r = await client.put("/api/admin/users/9999", json={
            "name": "Ghost"
        }, headers=_admin_headers())
        assert r.status_code == 404


# ── Delete user (soft) ──────────────────────────────────────────────


class TestDeleteUser:
    async def test_soft_delete_user(self, client):
        """Soft-delete sets is_active=False."""
        r = await client.delete("/api/admin/users/2", headers=_admin_headers())
        assert r.status_code == 204

        # Verify user is inactive
        r = await client.get("/api/admin/users/2", headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_delete_not_found(self, client):
        """Delete non-existent user returns 404."""
        r = await client.delete("/api/admin/users/9999", headers=_admin_headers())
        assert r.status_code == 404

    async def test_delete_dispatcher_forbidden(self, client):
        """DISPATCHER cannot delete users."""
        r = await client.delete("/api/admin/users/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Permission enforcement ──────────────────────────────────────────


class TestPermissionEnforcement:
    """Verify that read/write/delete permissions are enforced per resource."""

    async def test_dispatcher_cannot_list_users(self, client):
        r = await client.get("/api/admin/users", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_create_user(self, client):
        r = await client.post("/api/admin/users", json={
            "username": "hacker", "name": "Hacker",
            "password": "password123", "role_id": 2,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_update_user(self, client):
        r = await client.put("/api/admin/users/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403
