"""Integration tests for admin company info + system config endpoints."""

import pytest


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


# ── Company Info ───────────────────────────────────────────────────


class TestCompanyInfo:
    async def test_get_company_info(self, client):
        r = await client.get("/api/admin/company-info", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["ruc"] == "1790012345001"
        assert data["name"] == "TEST GAS"
        assert data["commercial_name"] == "TEST"

    async def test_update_name(self, client):
        r = await client.put("/api/admin/company-info", json={
            "name": "TEST GAS Actualizado",
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["name"] == "TEST GAS Actualizado"
        assert r.json()["ruc"] == "1790012345001"  # unchanged

    async def test_update_multiple_fields(self, client):
        r = await client.put("/api/admin/company-info", json={
            "commercial_name": "NEOGAS Estación",
            "phone": "02-345-6789",
            "city": "Quito",
            "province": "Pichincha",
            "sri_environment": 2,
        }, headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["commercial_name"] == "NEOGAS Estación"
        assert data["phone"] == "02-345-6789"
        assert data["sri_environment"] == 2

    async def test_clear_field(self, client):
        r = await client.put("/api/admin/company-info", json={
            "commercial_name": None,
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["commercial_name"] is None

    async def test_dispatcher_forbidden_get(self, client):
        r = await client.get(
            "/api/admin/company-info", headers=_dispatcher_headers()
        )
        assert r.status_code == 403

    async def test_dispatcher_forbidden_put(self, client):
        r = await client.put("/api/admin/company-info", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── System Config ──────────────────────────────────────────────────


class TestSystemConfig:
    async def test_list_all(self, client):
        r = await client.get("/api/admin/system-config", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 3  # seed has: accounting_branch_code, default_currency, key49_*
        keys = [c["key"] for c in data]
        assert "default_currency" in keys

    async def test_update_existing(self, client):
        r = await client.put("/api/admin/system-config/default_currency", json={
            "value": "EUR",
            "description": "ISO currency code",
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["value"] == "EUR"
        assert r.json()["description"] == "ISO currency code"

    async def test_create_new_key(self, client):
        """PUT on non-existing key creates it."""
        r = await client.put("/api/admin/system-config/new.feature.enabled", json={
            "value": "true",
            "description": "Enable new feature flag",
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["key"] == "new.feature.enabled"
        assert r.json()["value"] == "true"

    async def test_update_dispatcher_forbidden(self, client):
        r = await client.put("/api/admin/system-config/default_currency", json={
            "value": "HACKED"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403
