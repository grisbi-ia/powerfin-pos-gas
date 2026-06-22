"""Integration tests for admin payment methods CRUD endpoints."""

import pytest


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


class TestListPaymentMethods:
    async def test_list_all(self, client):
        r = await client.get("/api/admin/payment-methods", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 4  # EFECTIVO, TARJETA, CREDITO, YALOBOX from seed

    async def test_list_search(self, client):
        r = await client.get(
            "/api/admin/payment-methods?search=efectivo", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["code"] == "EFECTIVO"

    async def test_list_dispatcher_forbidden(self, client):
        r = await client.get(
            "/api/admin/payment-methods", headers=_dispatcher_headers()
        )
        assert r.status_code == 403


class TestCreatePaymentMethod:
    async def test_create_success(self, client):
        r = await client.post("/api/admin/payment-methods", json={
            "code": "QR",
            "name": "Pago QR",
            "sri_code": "20",
            "requires_reference": True,
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "QR"
        assert data["sri_code"] == "20"
        assert data["requires_reference"] is True

    async def test_create_duplicate_code(self, client):
        r = await client.post("/api/admin/payment-methods", json={
            "code": "EFECTIVO",
            "name": "Efectivo Duplicado",
        }, headers=_admin_headers())
        assert r.status_code == 409

    async def test_create_dispatcher_forbidden(self, client):
        r = await client.post("/api/admin/payment-methods", json={
            "code": "HACK", "name": "Hack",
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


class TestGetPaymentMethod:
    async def test_get_exists(self, client):
        r = await client.get("/api/admin/payment-methods/1", headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["code"] == "EFECTIVO"

    async def test_get_not_found(self, client):
        r = await client.get(
            "/api/admin/payment-methods/9999", headers=_admin_headers()
        )
        assert r.status_code == 404


class TestUpdatePaymentMethod:
    async def test_update_name(self, client):
        r = await client.put("/api/admin/payment-methods/1", json={
            "name": "Efectivo Actualizado"
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["name"] == "Efectivo Actualizado"

    async def test_update_sri_code(self, client):
        r = await client.put("/api/admin/payment-methods/1", json={
            "sri_code": "01"
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["sri_code"] == "01"

    async def test_deactivate(self, client):
        r = await client.put("/api/admin/payment-methods/1", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_dispatcher_forbidden(self, client):
        r = await client.put("/api/admin/payment-methods/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403
