"""Integration tests for admin price lists CRUD endpoints."""

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


# ── Price Lists CRUD ───────────────────────────────────────────────


class TestListPriceLists:
    async def test_list_all(self, client):
        r = await client.get("/api/admin/price-lists", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2  # STANDARD + VIP from seed
        codes = [i["code"] for i in data["items"]]
        assert "STANDARD" in codes
        assert "VIP" in codes

    async def test_list_includes_item_count(self, client):
        r = await client.get("/api/admin/price-lists", headers=_admin_headers())
        assert r.status_code == 200
        std = [i for i in r.json()["items"] if i["code"] == "STANDARD"][0]
        assert std["item_count"] >= 2  # DIESEL + SUPER items

    async def test_list_search(self, client):
        r = await client.get(
            "/api/admin/price-lists?search=vip", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["items"][0]["code"] == "VIP"

    async def test_list_pagination(self, client):
        r = await client.get(
            "/api/admin/price-lists?page=1&page_size=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    async def test_list_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/price-lists", headers=_dispatcher_headers())
        assert r.status_code == 403


class TestCreatePriceList:
    async def test_create_success(self, client):
        r = await client.post("/api/admin/price-lists", json={
            "code": "FAMILY",
            "name": "Precio Familiar",
            "is_default": False,
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["code"] == "FAMILY"
        assert data["name"] == "Precio Familiar"
        assert data["is_default"] is False
        assert data["is_active"] is True
        assert data["items"] == []

    async def test_create_duplicate_code(self, client):
        r = await client.post("/api/admin/price-lists", json={
            "code": "STANDARD",
            "name": "Duplicado",
        }, headers=_admin_headers())
        assert r.status_code == 409

    async def test_create_dispatcher_forbidden(self, client):
        r = await client.post("/api/admin/price-lists", json={
            "code": "HACK", "name": "Hack",
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


class TestGetPriceList:
    async def test_get_with_items(self, client):
        r = await client.get("/api/admin/price-lists/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == "STANDARD"
        assert len(data["items"]) >= 2
        # Each item has product info
        for item in data["items"]:
            assert "product_name" in item
            assert "product_code" in item
            assert "unit_price" in item

    async def test_get_not_found(self, client):
        r = await client.get("/api/admin/price-lists/9999", headers=_admin_headers())
        assert r.status_code == 404

    async def test_get_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/price-lists/1", headers=_dispatcher_headers())
        assert r.status_code == 403


class TestUpdatePriceList:
    async def test_update_name(self, client):
        r = await client.put("/api/admin/price-lists/1", json={
            "name": "Precio Normal Actualizado"
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["name"] == "Precio Normal Actualizado"
        assert r.json()["code"] == "STANDARD"

    async def test_update_default(self, client):
        r = await client.put("/api/admin/price-lists/2", json={
            "is_default": True
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_default"] is True

    async def test_update_deactivate(self, client):
        r = await client.put("/api/admin/price-lists/1", json={
            "is_active": False
        }, headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_not_found(self, client):
        r = await client.put("/api/admin/price-lists/9999", json={
            "name": "Ghost"
        }, headers=_admin_headers())
        assert r.status_code == 404

    async def test_update_dispatcher_forbidden(self, client):
        r = await client.put("/api/admin/price-lists/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


class TestDeletePriceList:
    async def test_soft_delete(self, client):
        r = await client.delete("/api/admin/price-lists/2", headers=_admin_headers())
        assert r.status_code == 204

        r = await client.get("/api/admin/price-lists/2", headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_delete_not_found(self, client):
        r = await client.delete("/api/admin/price-lists/9999", headers=_admin_headers())
        assert r.status_code == 404

    async def test_delete_dispatcher_forbidden(self, client):
        r = await client.delete("/api/admin/price-lists/1", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Price List Items CRUD ──────────────────────────────────────────


class TestListItemItems:
    async def test_list_items(self, client):
        r = await client.get("/api/admin/price-lists/1/items", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        codes = [i["product_code"] for i in data]
        assert "DIESEL" in codes

    async def test_list_items_includes_inactive(self, client):
        """Items endpoint also returns inactive items for admin visibility."""
        # First deactivate an item
        items = (await client.get(
            "/api/admin/price-lists/1/items", headers=_admin_headers()
        )).json()
        first_id = items[0]["price_list_item_id"]

        await client.delete(
            f"/api/admin/price-lists/1/items/{first_id}", headers=_admin_headers()
        )

        r = await client.get("/api/admin/price-lists/1/items", headers=_admin_headers())
        assert r.status_code == 200
        assert len(r.json()) == len(items)  # inactive still visible


class TestCreateItem:
    async def test_create_item_success(self, client):
        r = await client.post("/api/admin/price-lists/1/items", json={
            "product_id": 3,  # ACEITE
            "unit_price": 12.50,
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["product_id"] == 3
        assert data["product_name"] == "Aceite 20W50"
        assert data["unit_price"] == 12.50
        assert data["is_active"] is True

    async def test_create_item_duplicate_product(self, client):
        """Adding same product to same list returns 409."""
        # product_id=1 (DIESEL) already in price_list=1
        r = await client.post("/api/admin/price-lists/1/items", json={
            "product_id": 1,
            "unit_price": 3.50,
        }, headers=_admin_headers())
        assert r.status_code == 409

    async def test_create_item_reactivates_deleted(self, client):
        """Soft-deleted item is reactivated when re-created with same product."""
        # First get an item and delete it
        items = (await client.get(
            "/api/admin/price-lists/1/items", headers=_admin_headers()
        )).json()
        first_item = items[0]

        await client.delete(
            f"/api/admin/price-lists/1/items/{first_item['price_list_item_id']}",
            headers=_admin_headers()
        )

        # Re-create with same product
        r = await client.post("/api/admin/price-lists/1/items", json={
            "product_id": first_item["product_id"],
            "unit_price": 9.99,
        }, headers=_admin_headers())
        assert r.status_code == 201, r.text
        assert r.json()["unit_price"] == 9.99

    async def test_create_item_invalid_product(self, client):
        r = await client.post("/api/admin/price-lists/1/items", json={
            "product_id": 999,
            "unit_price": 10.00,
        }, headers=_admin_headers())
        assert r.status_code == 400

    async def test_create_item_invalid_price(self, client):
        r = await client.post("/api/admin/price-lists/1/items", json={
            "product_id": 3,
            "unit_price": 0,  # must be > 0
        }, headers=_admin_headers())
        assert r.status_code == 422

    async def test_create_item_dispatcher_forbidden(self, client):
        r = await client.post("/api/admin/price-lists/1/items", json={
            "product_id": 3, "unit_price": 10,
        }, headers=_dispatcher_headers())
        assert r.status_code == 403


class TestUpdateItem:
    async def test_update_price(self, client):
        items = (await client.get(
            "/api/admin/price-lists/1/items", headers=_admin_headers()
        )).json()
        item_id = items[0]["price_list_item_id"]

        r = await client.put(
            f"/api/admin/price-lists/1/items/{item_id}", json={
                "unit_price": 5.55
            }, headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["unit_price"] == 5.55

    async def test_update_deactivate(self, client):
        items = (await client.get(
            "/api/admin/price-lists/1/items", headers=_admin_headers()
        )).json()
        item_id = items[0]["price_list_item_id"]

        r = await client.put(
            f"/api/admin/price-lists/1/items/{item_id}", json={
                "is_active": False
            }, headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    async def test_update_item_not_found(self, client):
        r = await client.put("/api/admin/price-lists/1/items/9999", json={
            "unit_price": 1.00
        }, headers=_admin_headers())
        assert r.status_code == 404

    async def test_update_item_wrong_list(self, client):
        """Item from list 1 is not found under list 2."""
        r = await client.put("/api/admin/price-lists/2/items/1", json={
            "unit_price": 1.00
        }, headers=_admin_headers())
        assert r.status_code == 404


class TestDeleteItem:
    async def test_soft_delete_item(self, client):
        items = (await client.get(
            "/api/admin/price-lists/1/items", headers=_admin_headers()
        )).json()
        item_id = items[0]["price_list_item_id"]

        r = await client.delete(
            f"/api/admin/price-lists/1/items/{item_id}", headers=_admin_headers()
        )
        assert r.status_code == 204

    async def test_delete_item_not_found(self, client):
        r = await client.delete(
            "/api/admin/price-lists/1/items/9999", headers=_admin_headers()
        )
        assert r.status_code == 404


# ── Permission enforcement ──────────────────────────────────────────


class TestPermissionEnforcement:
    async def test_dispatcher_cannot_list(self, client):
        r = await client.get("/api/admin/price-lists", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_create(self, client):
        r = await client.post("/api/admin/price-lists", json={
            "code": "HACK", "name": "Hack",
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_update(self, client):
        r = await client.put("/api/admin/price-lists/1", json={
            "name": "Hacked"
        }, headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_dispatcher_cannot_delete(self, client):
        r = await client.delete("/api/admin/price-lists/1", headers=_dispatcher_headers())
        assert r.status_code == 403
