"""Integration tests for effective-dated product purchase costs."""

from datetime import date, timedelta


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


class TestProductCosts:
    async def test_product_detail_includes_current_cost(self, client):
        r = await client.get("/api/admin/products/1", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["cost_price"] == 2.60
        assert data["cost_source"] == "MANUAL"

    async def test_list_history_computes_valid_to(self, client):
        r = await client.get("/api/admin/products/1/costs", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["cost_price"] == 2.60
        assert data[0]["valid_to"] is None
        assert data[0]["is_current"] is True

    async def test_add_cost_creates_previous_valid_to(self, client):
        new_from = date.today() + timedelta(days=7)
        r = await client.post(
            "/api/admin/products/1/costs",
            headers=_admin_headers(),
            json={"valid_from": new_from.isoformat(), "cost_price": 2.75, "source": "MANUAL"},
        )
        assert r.status_code == 201
        assert r.json()["is_current"] is False

        r = await client.get("/api/admin/products/1/costs", headers=_admin_headers())
        rows = r.json()
        assert len(rows) == 2
        assert rows[0]["valid_to"] == (new_from - timedelta(days=1)).isoformat()
        assert rows[1]["valid_from"] == new_from.isoformat()

    async def test_same_date_upserts(self, client):
        r = await client.post(
            "/api/admin/products/1/costs",
            headers=_admin_headers(),
            json={"valid_from": "2026-01-01", "cost_price": 2.61, "source": "MANUAL"},
        )
        assert r.status_code == 201
        assert r.json()["cost_price"] == 2.61

        r = await client.get("/api/admin/products/1/costs", headers=_admin_headers())
        assert len(r.json()) == 1

    async def test_cannot_overwrite_other_source_without_force(self, client):
        r = await client.post(
            "/api/admin/products/1/costs",
            headers=_admin_headers(),
            json={"valid_from": "2026-01-01", "cost_price": 9.99, "source": "ERP"},
        )
        assert r.status_code == 409

        r = await client.post(
            "/api/admin/products/1/costs",
            headers=_admin_headers(),
            json={"valid_from": "2026-01-01", "cost_price": 9.99, "source": "ERP", "force": True},
        )
        assert r.status_code == 201
        assert r.json()["source"] == "ERP"

    async def test_update_and_delete_cost(self, client):
        r = await client.post(
            "/api/admin/products/1/costs",
            headers=_admin_headers(),
            json={"valid_from": "2026-02-01", "cost_price": 2.70, "source": "MANUAL"},
        )
        cost_id = r.json()["product_cost_id"]

        r = await client.put(
            f"/api/admin/products/1/costs/{cost_id}",
            headers=_admin_headers(),
            json={"cost_price": 2.72},
        )
        assert r.status_code == 200
        assert r.json()["cost_price"] == 2.72

        r = await client.delete(
            f"/api/admin/products/1/costs/{cost_id}", headers=_admin_headers()
        )
        assert r.status_code == 204

    async def test_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/products/1/costs", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_unknown_product(self, client):
        r = await client.get("/api/admin/products/9999/costs", headers=_admin_headers())
        assert r.status_code == 404
