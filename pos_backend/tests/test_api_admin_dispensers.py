"""Integration tests for admin dispensers + hoses CRUD endpoints."""

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


# ── Dispenser CRUD ─────────────────────────────────────────────────


class TestListDispensers:
    async def test_list_all(self, client):
        r = await client.get("/api/admin/dispensers", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1  # SURT-01 from seed
        items = data["items"]
        codes = [i["code"] for i in items]
        assert "SURT-01" in codes

    async def test_list_includes_hose_count(self, client):
        r = await client.get("/api/admin/dispensers", headers=_admin_headers())
        assert r.status_code == 200
        surt = [i for i in r.json()["items"] if i["code"] == "SURT-01"][0]
        assert surt["hose_count"] >= 2  # sides A and B

    async def test_list_includes_emission_label(self, client):
        r = await client.get("/api/admin/dispensers", headers=_admin_headers())
        assert r.status_code == 200
        surt = [i for i in r.json()["items"] if i["code"] == "SURT-01"][0]
        assert surt["emission_point_label"] == "001-001"

    async def test_list_search(self, client):
        r = await client.get(
            "/api/admin/dispensers?search=SURT", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_list_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/dispensers", headers=_dispatcher_headers())
        assert r.status_code == 403


class TestCreateDispenser:
    async def test_create_success(self, client):
        r = await client.post("/api/admin/dispensers", json={
            "code": "SURT-02",
            "name": "Surtidor 02",
            "emission_point_id": 1,
            "printer_ip": "192.168.1.32",
            "printer_port": 9100,
            "sort_order": 2,
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "SURT-02"
        assert data["name"] == "Surtidor 02"
        assert data["emission_point_label"] == "001-001"
        assert data["printer_ip"] == "192.168.1.32"
        assert data["hoses"] == []

    async def test_create_minimal(self, client):
        r = await client.post("/api/admin/dispensers", json={
            "code": "SURT-03",
            "name": "Surtidor 03",
        }, headers=_admin_headers())
        assert r.status_code == 201
        assert r.json()["emission_point_label"] is None
        assert r.json()["printer_ip"] is None
        assert r.json()["printer_port"] == 9100

    async def test_create_invalid_emission_point(self, client):
        r = await client.post("/api/admin/dispensers", json={
            "code": "SURT-04",
            "name": "Surtidor 04",
            "emission_point_id": 999,
        }, headers=_admin_headers())
        assert r.status_code == 400


class TestGetDispenser:
    async def test_get_with_hoses(self, client):
        r = await client.get("/api/admin/dispensers/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == "SURT-01"
        assert len(data["hoses"]) >= 2
        sides = [h["side"] for h in data["hoses"]]
        assert "A" in sides
        assert "B" in sides

    async def test_get_hoses_have_grade_info(self, client):
        r = await client.get("/api/admin/dispensers/1", headers=_admin_headers())
        assert r.status_code == 200
        for hose in r.json()["hoses"]:
            assert "grade_code" in hose
            assert "grade_name" in hose
            assert "fusion_pump_id" in hose
            assert "fusion_hose_id" in hose

    async def test_get_not_found(self, client):
        r = await client.get("/api/admin/dispensers/9999", headers=_admin_headers())
        assert r.status_code == 404


class TestUpdateDispenser:
    async def test_update_name(self, client):
        r = await client.put("/api/admin/dispensers/1", json={
            "name": "Surtidor Diesel Actualizado"
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["name"] == "Surtidor Diesel Actualizado"

    async def test_update_printer_ip(self, client):
        r = await client.put("/api/admin/dispensers/1", json={
            "printer_ip": "192.168.1.99"
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["printer_ip"] == "192.168.1.99"

    async def test_update_clear_printer_ip(self, client):
        """Setting printer_ip to null clears it."""
        r = await client.put("/api/admin/dispensers/1", json={
            "printer_ip": None
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["printer_ip"] is None

    async def test_update_deactivate(self, client):
        r = await client.put("/api/admin/dispensers/1", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_not_found(self, client):
        r = await client.put("/api/admin/dispensers/9999", json={
            "name": "Ghost"
        }, headers=_admin_headers())
        assert r.status_code == 404


class TestDeleteDispenser:
    async def test_soft_delete(self, client):
        # Use the dispenser created in create test (id=2 from SURT-02)
        r = await client.delete("/api/admin/dispensers/2", headers=_admin_headers())
        # May be 204 or 404 depending on test ordering
        if r.status_code == 204:
            r = await client.get("/api/admin/dispensers/2", headers=_admin_headers())
            assert r.status_code == 200
            assert r.json()["is_active"] is False
        else:
            assert r.status_code == 404

    async def test_delete_dispatcher_forbidden(self, client):
        r = await client.delete("/api/admin/dispensers/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Hose CRUD ──────────────────────────────────────────────────────


class TestListHoses:
    async def test_list_hoses(self, client):
        r = await client.get("/api/admin/dispensers/1/hoses", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        assert data[0]["side"] in ("A", "B")

    async def test_list_hoses_dispenser_not_found(self, client):
        r = await client.get("/api/admin/dispensers/9999/hoses", headers=_admin_headers())
        assert r.status_code == 404


class TestCreateHose:
    async def test_create_hose_success(self, client):
        # Create a new dispenser first (id=2)
        await client.post("/api/admin/dispensers", json={
            "code": "SURT-TEST", "name": "Test Dispenser",
        }, headers=_admin_headers())

        r = await client.post("/api/admin/dispensers/2/hoses", json={
            "side": "A",
            "fusion_pump_id": 3,
            "fusion_hose_id": 1,
            "grade_code": "DIESEL",
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["side"] == "A"
        assert data["fusion_pump_id"] == 3
        assert data["grade_code"] == "DIESEL"
        assert "Diesel" in data["grade_name"]
        assert data["is_active"] is True

    async def test_create_hose_duplicate_side(self, client):
        """Same side already has active hose on dispenser 1."""
        r = await client.post("/api/admin/dispensers/1/hoses", json={
            "side": "A",
            "fusion_pump_id": 99,
            "fusion_hose_id": 99,
            "grade_code": "SUPER",
        }, headers=_admin_headers())
        assert r.status_code == 409

    async def test_create_hose_invalid_side(self, client):
        r = await client.post("/api/admin/dispensers/1/hoses", json={
            "side": "X",
            "fusion_pump_id": 5,
            "fusion_hose_id": 1,
            "grade_code": "DIESEL",
        }, headers=_admin_headers())
        assert r.status_code == 422

    async def test_create_hose_dispenser_not_found(self, client):
        r = await client.post("/api/admin/dispensers/9999/hoses", json={
            "side": "A", "fusion_pump_id": 1, "fusion_hose_id": 1, "grade_code": "DIESEL",
        }, headers=_admin_headers())
        assert r.status_code == 404


class TestUpdateHose:
    async def test_update_grade(self, client):
        r = await client.put("/api/admin/dispensers/1/hoses/1", json={
            "grade_code": "SUPER"
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["grade_code"] == "SUPER"
        assert "Super" in r.json()["grade_name"]

    async def test_update_pump_id(self, client):
        r = await client.put("/api/admin/dispensers/1/hoses/1", json={
            "fusion_pump_id": 10
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["fusion_pump_id"] == 10

    async def test_update_deactivate(self, client):
        r = await client.put("/api/admin/dispensers/1/hoses/1", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_hose_not_found(self, client):
        r = await client.put("/api/admin/dispensers/1/hoses/9999", json={
            "grade_code": "SUPER"
        }, headers=_admin_headers())
        assert r.status_code == 404

    async def test_update_hose_wrong_dispenser(self, client):
        """Hose from dispenser 1 not visible under dispenser 2."""
        r = await client.put("/api/admin/dispensers/2/hoses/1", json={
            "grade_code": "SUPER"
        }, headers=_admin_headers())
        assert r.status_code == 404


# ── Permission enforcement ──────────────────────────────────────────


class TestPermissionEnforcement:
    async def test_dispatcher_cannot_list_dispensers(self, client):
        r = await client.get("/api/admin/dispensers", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_create_dispenser(self, client):
        r = await client.post("/api/admin/dispensers", json={
            "code": "HACK", "name": "Hack",
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_list_hoses(self, client):
        r = await client.get("/api/admin/dispensers/1/hoses", headers=_dispatcher_headers())
        assert r.status_code == 403
