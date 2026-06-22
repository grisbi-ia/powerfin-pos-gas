"""Integration tests for admin products CRUD endpoints."""

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


# ── List products ──────────────────────────────────────────────────


class TestListProducts:
    async def test_list_all_products(self, client):
        """Admin can list all products with pagination."""
        r = await client.get("/api/admin/products", headers=_admin_headers())
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] >= 3  # DIESEL, SUPER, ACEITE from seed
        assert data["page"] == 1
        assert "items" in data

    async def test_list_pagination(self, client):
        r = await client.get(
            "/api/admin/products?page=1&page_size=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert data["page_size"] == 1

    async def test_list_search_by_name(self, client):
        r = await client.get(
            "/api/admin/products?search=diesel", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["code"] == "DIESEL"

    async def test_list_search_by_code(self, client):
        r = await client.get(
            "/api/admin/products?search=SUPER", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        codes = [item["code"] for item in data["items"]]
        assert "SUPER" in codes

    async def test_list_filter_by_category(self, client):
        r = await client.get(
            "/api/admin/products?category=OIL", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert item["category_name"] == "Aceites"

    async def test_list_filter_by_fuel_category(self, client):
        r = await client.get(
            "/api/admin/products?category=FUEL", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert item["category_name"] == "Combustibles"

    async def test_list_sort_desc(self, client):
        r = await client.get(
            "/api/admin/products?sort=code&order=desc", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        codes = [item["code"] for item in data["items"]]
        assert codes == sorted(codes, reverse=True)

    async def test_list_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/products", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Create product ──────────────────────────────────────────────────


class TestCreateProduct:
    async def test_create_product_success(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "ECO",
            "name": "Eco Plus",
            "category_id": 1,  # FUEL
            "unit": "GAL",
            "base_price": 2.850,
            "subsidy_per_unit": 0.50,
            "tax_type_id": 1,  # IVA_15
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "ECO"
        assert data["name"] == "Eco Plus"
        assert data["category_name"] == "Combustibles"
        assert data["is_fuel"] is True
        assert data["base_price"] == 2.850
        assert data["subsidy_per_unit"] == 0.50
        assert data["tax_type_name"] == "IVA 15%"
        assert data["tax_rate"] == 0.15
        assert data["is_active"] is True

    async def test_create_product_minimal(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "FILTRO",
            "name": "Filtro de Aire",
            "category_id": 2,  # OIL
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "FILTRO"
        assert data["name"] == "Filtro de Aire"
        assert data["unit"] == "UNIDAD"  # default
        assert data["base_price"] == 0

    async def test_create_product_duplicate_code(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "DIESEL",  # already exists
            "name": "Diesel Duplicado",
            "category_id": 1,
        }, headers=_admin_headers())
        assert r.status_code == 409, r.text
        assert "ya existe" in r.json()["detail"]

    async def test_create_product_invalid_category(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "TEST",
            "name": "Test",
            "category_id": 999,
        }, headers=_admin_headers())
        assert r.status_code == 400
        assert "no encontrada" in r.json()["detail"]

    async def test_create_product_invalid_tax_type(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "TEST2",
            "name": "Test 2",
            "category_id": 1,
            "tax_type_id": 999,
        }, headers=_admin_headers())
        assert r.status_code == 400
        assert "no encontrado" in r.json()["detail"]

    async def test_create_product_invalid_code_format(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "eco",  # lowercase not allowed
            "name": "Eco Lowercase",
            "category_id": 1,
        }, headers=_admin_headers())
        assert r.status_code == 422

    async def test_create_product_dispatcher_forbidden(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "HACK",
            "name": "Hacked",
            "category_id": 1,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Get product ─────────────────────────────────────────────────────


class TestGetProduct:
    async def test_get_product_exists(self, client):
        r = await client.get("/api/admin/products/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["product_id"] == 1
        assert data["code"] == "DIESEL"
        assert data["name"] == "Diesel"
        assert data["category_name"] == "Combustibles"
        assert data["is_fuel"] is True
        assert data["unit"] == "GAL"
        assert data["tax_type_name"] == "IVA 15%"

    async def test_get_product_not_found(self, client):
        r = await client.get("/api/admin/products/9999", headers=_admin_headers())
        assert r.status_code == 404
        assert "Producto no encontrado" in r.json()["detail"]

    async def test_get_product_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/products/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Update product ──────────────────────────────────────────────────


class TestUpdateProduct:
    async def test_update_name(self, client):
        r = await client.put("/api/admin/products/1", json={
            "name": "Diesel Premium"
        }, headers=_admin_headers())
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Diesel Premium"
        assert r.json()["code"] == "DIESEL"  # code unchanged

    async def test_update_base_price(self, client):
        r = await client.put("/api/admin/products/1", json={
            "base_price": 3.500
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["base_price"] == 3.500

    async def test_update_subsidy(self, client):
        r = await client.put("/api/admin/products/1", json={
            "subsidy_per_unit": 1.25
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["subsidy_per_unit"] == 1.25

    async def test_update_clear_subsidy(self, client):
        """Setting subsidy_per_unit to null clears it."""
        # First set it
        await client.put("/api/admin/products/1", json={
            "subsidy_per_unit": 1.0
        }, headers=_admin_headers())
        # Then clear it — sending None
        r = await client.put("/api/admin/products/1", json={
            "subsidy_per_unit": None
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["subsidy_per_unit"] is None

    async def test_update_category(self, client):
        r = await client.put("/api/admin/products/3", json={
            "category_id": 2  # OIL category
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["category_id"] == 2
        assert r.json()["category_name"] == "Aceites"
        assert r.json()["is_fuel"] is False

    async def test_update_tax_type(self, client):
        r = await client.put("/api/admin/products/2", json={
            "tax_type_id": 2  # IVA_0
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["tax_type_id"] == 2
        assert r.json()["tax_type_name"] == "IVA 0%"
        assert r.json()["tax_rate"] == 0.0

    async def test_update_deactivate(self, client):
        r = await client.put("/api/admin/products/1", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_not_found(self, client):
        r = await client.put("/api/admin/products/9999", json={
            "name": "Ghost"
        }, headers=_admin_headers())
        assert r.status_code == 404

    async def test_update_invalid_category(self, client):
        r = await client.put("/api/admin/products/1", json={
            "category_id": 999
        }, headers=_admin_headers())
        assert r.status_code == 400

    async def test_update_dispatcher_forbidden(self, client):
        r = await client.put("/api/admin/products/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Delete product (soft) ───────────────────────────────────────────


class TestDeleteProduct:
    async def test_soft_delete_product(self, client):
        r = await client.delete("/api/admin/products/3", headers=_admin_headers())
        assert r.status_code == 204

        # Verify is_active is False
        r = await client.get("/api/admin/products/3", headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_deleted_product_does_not_appear_in_pos(self, client):
        """Soft-deleted product is excluded from POS product list."""
        # Delete product 3
        await client.delete("/api/admin/products/3", headers=_admin_headers())

        # POS product list should exclude it
        from app.services.auth_service import create_access_token
        pos_headers = {
            "Authorization": f"Bearer {create_access_token(2, 'carlos')}"
        }
        r = await client.get("/api/pos/products", headers=pos_headers)
        assert r.status_code == 200
        codes = [p["code"] for p in r.json()]
        assert "ACEITE" not in codes  # product 3 was ACEITE
        assert "DIESEL" in codes  # other products still there

    async def test_delete_not_found(self, client):
        r = await client.delete("/api/admin/products/9999", headers=_admin_headers())
        assert r.status_code == 404

    async def test_delete_dispatcher_forbidden(self, client):
        r = await client.delete("/api/admin/products/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Permission enforcement ──────────────────────────────────────────


class TestPermissionEnforcement:
    async def test_dispatcher_cannot_list_products(self, client):
        r = await client.get("/api/admin/products", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_create_product(self, client):
        r = await client.post("/api/admin/products", json={
            "code": "HACK", "name": "Hack", "category_id": 1,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_update_product(self, client):
        r = await client.put("/api/admin/products/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_delete_product(self, client):
        r = await client.delete("/api/admin/products/1", headers=_dispatcher_headers())
        assert r.status_code == 403
