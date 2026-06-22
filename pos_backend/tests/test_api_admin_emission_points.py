"""Integration tests for admin emission points CRUD endpoints."""

import pytest


# ── Helpers ────────────────────────────────────────────────────────


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


# ── List emission points ───────────────────────────────────────────


class TestListEmissionPoints:
    async def test_list_all(self, client):
        r = await client.get("/api/admin/emission-points", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1  # 001-001 from seed
        items = data["items"]
        assert items[0]["label"] == "001-001"
        assert items[0]["doc_type"] == "FACTURA"

    async def test_list_pagination(self, client):
        r = await client.get(
            "/api/admin/emission-points?page=1&page_size=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    async def test_list_search(self, client):
        r = await client.get(
            "/api/admin/emission-points?search=001", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_list_dispatcher_forbidden(self, client):
        r = await client.get(
            "/api/admin/emission-points", headers=_dispatcher_headers()
        )
        assert r.status_code == 403


# ── Create emission point ──────────────────────────────────────────


class TestCreateEmissionPoint:
    async def test_create_success(self, client):
        r = await client.post("/api/admin/emission-points", json={
            "establishment": "001",
            "emission_point": "002",
            "doc_type": "FACTURA",
            "sequential_start": 1,
            "sequential_end": 9999,
            "authorization_number": "AUTH-123",
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["label"] == "001-002"
        assert data["doc_type"] == "FACTURA"
        assert data["current_sequential"] == 1  # starts at sequential_start
        assert data["authorization_number"] == "AUTH-123"

    async def test_create_minimal(self, client):
        r = await client.post("/api/admin/emission-points", json={
            "establishment": "002",
            "emission_point": "001",
            "sequential_start": 100,
            "sequential_end": 500,
        }, headers=_admin_headers())
        assert r.status_code == 201
        assert r.json()["label"] == "002-001"
        assert r.json()["doc_type"] == "FACTURA"  # default

    async def test_create_duplicate_pair(self, client):
        r = await client.post("/api/admin/emission-points", json={
            "establishment": "001",
            "emission_point": "001",  # already exists from seed
            "sequential_start": 1,
            "sequential_end": 500,
        }, headers=_admin_headers())
        assert r.status_code == 409

    async def test_create_dispatcher_forbidden(self, client):
        r = await client.post("/api/admin/emission-points", json={
            "establishment": "999", "emission_point": "999",
            "sequential_start": 1, "sequential_end": 100,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Get emission point ─────────────────────────────────────────────


class TestGetEmissionPoint:
    async def test_get_exists(self, client):
        r = await client.get("/api/admin/emission-points/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["label"] == "001-001"
        assert data["sequential_start"] == 1
        assert data["sequential_end"] == 9999

    async def test_get_not_found(self, client):
        r = await client.get(
            "/api/admin/emission-points/9999", headers=_admin_headers()
        )
        assert r.status_code == 404


# ── Update emission point ──────────────────────────────────────────


class TestUpdateEmissionPoint:
    async def test_update_sequential_range(self, client):
        r = await client.put("/api/admin/emission-points/1", json={
            "sequential_start": 500,
            "sequential_end": 10000,
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["sequential_start"] == 500
        assert r.json()["sequential_end"] == 10000

    async def test_update_current_sequential(self, client):
        r = await client.put("/api/admin/emission-points/1", json={
            "current_sequential": 150
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["current_sequential"] == 150

    async def test_update_authorization(self, client):
        r = await client.put("/api/admin/emission-points/1", json={
            "authorization_number": "NEW-AUTH-456",
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["authorization_number"] == "NEW-AUTH-456"

    async def test_update_clear_authorization(self, client):
        await client.put("/api/admin/emission-points/1", json={
            "authorization_number": "TEMP",
        }, headers=_admin_headers())
        r = await client.put("/api/admin/emission-points/1", json={
            "authorization_number": None,
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["authorization_number"] is None

    async def test_update_deactivate(self, client):
        r = await client.put("/api/admin/emission-points/1", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_not_found(self, client):
        r = await client.put("/api/admin/emission-points/9999", json={
            "doc_type": "NOTA_CREDITO"
        }, headers=_admin_headers())
        assert r.status_code == 404

    async def test_update_dispatcher_forbidden(self, client):
        r = await client.put("/api/admin/emission-points/1", json={
            "is_active": False
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Permission enforcement ──────────────────────────────────────────


class TestPermissionEnforcement:
    async def test_dispatcher_cannot_list(self, client):
        r = await client.get(
            "/api/admin/emission-points", headers=_dispatcher_headers()
        )
        assert r.status_code == 403

    async def test_dispatcher_cannot_create(self, client):
        r = await client.post("/api/admin/emission-points", json={
            "establishment": "999", "emission_point": "999",
            "sequential_start": 1, "sequential_end": 100,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403
