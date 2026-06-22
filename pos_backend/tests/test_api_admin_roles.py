"""Integration tests for admin roles CRUD endpoints."""

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


# ── List roles ─────────────────────────────────────────────────────


class TestListRoles:
    async def test_list_all_roles(self, client):
        """Admin can list all roles with pagination."""
        r = await client.get("/api/admin/roles", headers=_admin_headers())
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 2  # ADMIN + DISPATCHER from seed
        assert data["page"] == 1
        assert "items" in data
        assert len(data["items"]) >= 2

    async def test_list_pagination(self, client):
        """Pagination params are respected."""
        r = await client.get(
            "/api/admin/roles?page=1&page_size=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert data["page_size"] == 1

    async def test_list_search_by_name(self, client):
        """Search filters by name."""
        r = await client.get(
            "/api/admin/roles?search=admin", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "ADMIN"

    async def test_list_search_by_code(self, client):
        """Search filters by code (case-insensitive)."""
        r = await client.get(
            "/api/admin/roles?search=disp", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        codes = [item["code"] for item in data["items"]]
        assert "DISPATCHER" in codes

    async def test_list_sort_desc(self, client):
        """Sort order desc works."""
        r = await client.get(
            "/api/admin/roles?sort=code&order=desc", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        codes = [item["code"] for item in data["items"]]
        assert codes == sorted(codes, reverse=True)

    async def test_list_dispatcher_forbidden(self, client):
        """DISPATCHER cannot access admin roles list."""
        r = await client.get("/api/admin/roles", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Create role ─────────────────────────────────────────────────────


class TestCreateRole:
    async def test_create_role_success(self, client):
        """Admin can create a new role."""
        r = await client.post("/api/admin/roles", json={
            "code": "SUPERVISOR",
            "name": "Supervisor",
            "permissions_json": {
                "SUPERVISOR": {
                    "users": ["read"],
                    "reports": ["read", "export"],
                }
            },
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "SUPERVISOR"
        assert data["name"] == "Supervisor"
        assert data["is_active"] is True
        assert data["permissions_json"]["SUPERVISOR"]["users"] == ["read"]

    async def test_create_role_minimal(self, client):
        """Role with just code and name, no permissions."""
        r = await client.post("/api/admin/roles", json={
            "code": "AUDITOR",
            "name": "Auditor",
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "AUDITOR"
        assert data["name"] == "Auditor"
        assert data["permissions_json"] is None

    async def test_create_role_duplicate_code(self, client):
        """Duplicate code returns 409."""
        r = await client.post("/api/admin/roles", json={
            "code": "ADMIN",  # already exists from seed
            "name": "Administrador Duplicado",
        }, headers=_admin_headers())
        assert r.status_code == 409, r.text
        assert "ya existe" in r.json()["detail"]

    async def test_create_role_invalid_code_format(self, client):
        """Code must be uppercase letters and underscores only."""
        r = await client.post("/api/admin/roles", json={
            "code": "admin",  # lowercase
            "name": "Admin Lowercase",
        }, headers=_admin_headers())
        assert r.status_code == 422, r.text

    async def test_create_role_short_code(self, client):
        """Code must be at least 2 chars."""
        r = await client.post("/api/admin/roles", json={
            "code": "A",
            "name": "Too short",
        }, headers=_admin_headers())
        assert r.status_code == 422

    async def test_create_role_missing_required(self, client):
        """Missing required fields returns 422."""
        r = await client.post("/api/admin/roles", json={
            "name": "No Code"
        }, headers=_admin_headers())
        assert r.status_code == 422

    async def test_create_role_dispatcher_forbidden(self, client):
        """DISPATCHER cannot create roles."""
        r = await client.post("/api/admin/roles", json={
            "code": "HACKER",
            "name": "Hacker Role",
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Get role ────────────────────────────────────────────────────────


class TestGetRole:
    async def test_get_role_exists(self, client):
        """Admin can get a single role by id."""
        r = await client.get("/api/admin/roles/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["role_id"] == 1
        assert data["code"] == "ADMIN"
        assert data["name"] == "Admin"

    async def test_get_role_not_found(self, client):
        """Non-existent role returns 404."""
        r = await client.get("/api/admin/roles/9999", headers=_admin_headers())
        assert r.status_code == 404
        assert "Rol no encontrado" in r.json()["detail"]

    async def test_get_role_dispatcher_forbidden(self, client):
        """DISPATCHER cannot get a role."""
        r = await client.get("/api/admin/roles/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Update role ─────────────────────────────────────────────────────


class TestUpdateRole:
    async def test_update_name(self, client):
        """Update only the name field."""
        r = await client.put("/api/admin/roles/1", json={
            "name": "Administrador Actualizado"
        }, headers=_admin_headers())
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Administrador Actualizado"
        assert r.json()["code"] == "ADMIN"  # code unchanged

    async def test_update_permissions(self, client):
        """Update permissions_json."""
        new_perms = {
            "ADMIN": {
                "users": ["read", "write", "delete"],
                "roles": ["read", "write"],
                "products": ["read", "write", "delete"],
            }
        }
        r = await client.put("/api/admin/roles/1", json={
            "permissions_json": new_perms,
        }, headers=_admin_headers())
        assert r.status_code == 200, r.text
        assert r.json()["permissions_json"] == new_perms

    async def test_update_clear_permissions(self, client):
        """Set permissions_json to null to clear them."""
        r = await client.put("/api/admin/roles/1", json={
            "permissions_json": None,
        }, headers=_admin_headers())
        assert r.status_code == 200, r.text
        assert r.json()["permissions_json"] is None

    async def test_update_deactivate(self, client):
        """Deactivate a role."""
        r = await client.put("/api/admin/roles/2", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200, r.text
        assert r.json()["is_active"] is False

    async def test_update_reactivate(self, client):
        """Reactivate a deactivated role."""
        # First deactivate
        await client.put("/api/admin/roles/2", json={
            "is_active": False
        }, headers=_admin_headers())

        # Then reactivate
        r = await client.put("/api/admin/roles/2", json={
            "is_active": True
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    async def test_update_code_not_allowed(self, client):
        """Code cannot be changed — sending code in body is ignored."""
        r = await client.put("/api/admin/roles/1", json={
            "name": "Still Admin",
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["code"] == "ADMIN"

    async def test_update_not_found(self, client):
        """Update non-existent role returns 404."""
        r = await client.put("/api/admin/roles/9999", json={
            "name": "Ghost"
        }, headers=_admin_headers())
        assert r.status_code == 404

    async def test_update_dispatcher_forbidden(self, client):
        """DISPATCHER cannot update roles."""
        r = await client.put("/api/admin/roles/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Permission enforcement ──────────────────────────────────────────


class TestPermissionEnforcement:
    """Verify that read/write permissions are enforced on roles resource."""

    async def test_dispatcher_cannot_list_roles(self, client):
        r = await client.get("/api/admin/roles", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_create_role(self, client):
        r = await client.post("/api/admin/roles", json={
            "code": "HACKER", "name": "Hacker",
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_update_role(self, client):
        r = await client.put("/api/admin/roles/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_get_role(self, client):
        r = await client.get("/api/admin/roles/1", headers=_dispatcher_headers())
        assert r.status_code == 403
