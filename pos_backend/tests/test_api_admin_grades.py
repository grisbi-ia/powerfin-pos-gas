"""Integration tests for admin grades CRUD endpoints."""

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


# ── List grades ────────────────────────────────────────────────────


class TestListGrades:
    async def test_list_all_grades(self, client):
        r = await client.get("/api/admin/grades", headers=_admin_headers())
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 2  # DIESEL + SUPER from seed
        assert data["page"] == 1
        items = data["items"]
        codes = [i["code"] for i in items]
        assert "DIESEL" in codes
        assert "SUPER" in codes

    async def test_list_pagination(self, client):
        r = await client.get(
            "/api/admin/grades?page=1&page_size=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1

    async def test_list_search_by_name(self, client):
        r = await client.get(
            "/api/admin/grades?search=diesel", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "DIESEL"

    async def test_list_search_by_code(self, client):
        r = await client.get(
            "/api/admin/grades?search=SUP", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        codes = [i["code"] for i in data["items"]]
        assert "SUPER" in codes

    async def test_list_sort_desc(self, client):
        r = await client.get(
            "/api/admin/grades?sort=code&order=desc", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        codes = [i["code"] for i in data["items"]]
        assert codes == sorted(codes, reverse=True)

    async def test_list_includes_product_info(self, client):
        """List items include product_name and product_code."""
        r = await client.get("/api/admin/grades", headers=_admin_headers())
        assert r.status_code == 200
        diesel = [i for i in r.json()["items"] if i["code"] == "DIESEL"][0]
        assert diesel["product_name"] == "Diesel"
        assert diesel["product_code"] == "DIESEL"

    async def test_list_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/grades", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Create grade ────────────────────────────────────────────────────


class TestCreateGrade:
    async def test_create_grade_success(self, client):
        r = await client.post("/api/admin/grades", json={
            "code": "ECO",
            "name": "Eco Plus",
            "product_id": 1,  # DIESEL product
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "ECO"
        assert data["name"] == "Eco Plus"
        assert data["product_id"] == 1
        assert data["product_name"] == "Diesel"
        assert data["product_code"] == "DIESEL"
        assert data["is_active"] is True

    async def test_create_grade_duplicate_code(self, client):
        r = await client.post("/api/admin/grades", json={
            "code": "DIESEL",  # already exists
            "name": "Diesel Duplicado",
            "product_id": 1,
        }, headers=_admin_headers())
        assert r.status_code == 409
        assert "ya existe" in r.json()["detail"]

    async def test_create_grade_invalid_product(self, client):
        r = await client.post("/api/admin/grades", json={
            "code": "TEST",
            "name": "Test Grade",
            "product_id": 999,
        }, headers=_admin_headers())
        assert r.status_code == 400
        assert "no encontrado" in r.json()["detail"]

    async def test_create_grade_dispatcher_forbidden(self, client):
        r = await client.post("/api/admin/grades", json={
            "code": "HACK", "name": "Hack", "product_id": 1,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Get grade ───────────────────────────────────────────────────────


class TestGetGrade:
    async def test_get_grade_exists(self, client):
        r = await client.get("/api/admin/grades/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["grade_id"] == 1
        assert data["code"] == "DIESEL"
        assert data["name"] == "Diesel"
        assert data["product_name"] == "Diesel"
        assert data["product_unit"] == "GAL"

    async def test_get_grade_not_found(self, client):
        r = await client.get("/api/admin/grades/9999", headers=_admin_headers())
        assert r.status_code == 404
        assert "Grado no encontrado" in r.json()["detail"]

    async def test_get_grade_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/grades/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Update grade ────────────────────────────────────────────────────


class TestUpdateGrade:
    async def test_update_name(self, client):
        r = await client.put("/api/admin/grades/1", json={
            "name": "Diesel Actualizado"
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["name"] == "Diesel Actualizado"
        assert r.json()["code"] == "DIESEL"  # code unchanged

    async def test_update_product(self, client):
        """Change the product linked to a grade."""
        r = await client.put("/api/admin/grades/2", json={
            "product_id": 1  # change SUPER grade to use DIESEL product
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["product_id"] == 1
        assert r.json()["product_name"] == "Diesel"

    async def test_update_deactivate(self, client):
        r = await client.put("/api/admin/grades/1", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_reactivate(self, client):
        await client.put("/api/admin/grades/1", json={
            "is_active": False
        }, headers=_admin_headers())
        r = await client.put("/api/admin/grades/1", json={
            "is_active": True
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    async def test_update_not_found(self, client):
        r = await client.put("/api/admin/grades/9999", json={
            "name": "Ghost"
        }, headers=_admin_headers())
        assert r.status_code == 404

    async def test_update_invalid_product(self, client):
        r = await client.put("/api/admin/grades/1", json={
            "product_id": 999
        }, headers=_admin_headers())
        assert r.status_code == 400

    async def test_update_dispatcher_forbidden(self, client):
        r = await client.put("/api/admin/grades/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Delete grade (soft) ─────────────────────────────────────────────


class TestDeleteGrade:
    async def test_soft_delete_grade(self, client):
        r = await client.delete("/api/admin/grades/2", headers=_admin_headers())
        assert r.status_code == 204

        r = await client.get("/api/admin/grades/2", headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_delete_not_found(self, client):
        r = await client.delete("/api/admin/grades/9999", headers=_admin_headers())
        assert r.status_code == 404

    async def test_delete_dispatcher_forbidden(self, client):
        r = await client.delete("/api/admin/grades/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Permission enforcement ──────────────────────────────────────────


class TestPermissionEnforcement:
    async def test_dispatcher_cannot_list_grades(self, client):
        r = await client.get("/api/admin/grades", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_create_grade(self, client):
        r = await client.post("/api/admin/grades", json={
            "code": "HACK", "name": "Hack", "product_id": 1,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_update_grade(self, client):
        r = await client.put("/api/admin/grades/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_delete_grade(self, client):
        r = await client.delete("/api/admin/grades/1", headers=_dispatcher_headers())
        assert r.status_code == 403
