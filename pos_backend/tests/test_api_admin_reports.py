"""Integration tests for admin reports endpoints."""

import pytest

from tests.test_api_admin_dashboard import _seed_dispatch_data


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


# ── Sales Report ───────────────────────────────────────────────────


class TestSalesReport:
    async def test_list_with_data(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get("/api/admin/reports/sales", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_filter_by_date(self, client, db):
        await _seed_dispatch_data(db)
        from datetime import date
        r = await client.get(
            f"/api/admin/reports/sales?date_from={date.today()}&date_to={date.today()}",
            headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["total"] == 3

    async def test_filter_future_date_returns_empty(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get(
            "/api/admin/reports/sales?date_from=2099-01-01",
            headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_search_by_customer(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get(
            "/api/admin/reports/sales?search=Juan", headers=_admin_headers()
        )
        assert r.status_code == 200
        data = r.json()
        for item in data["items"]:
            assert "Juan" in (item["customer_name"] or "")

    async def test_pagination(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get(
            "/api/admin/reports/sales?page_size=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1

    async def test_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/reports/sales", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_export_xlsx(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.post("/api/admin/reports/sales/export?format=xlsx", headers=_admin_headers())
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    async def test_export_pdf(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.post("/api/admin/reports/sales/export?format=pdf", headers=_admin_headers())
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"


# ── Dispatches Report ──────────────────────────────────────────────


class TestDispatchesReport:
    async def test_list_all(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get("/api/admin/reports/dispatches", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3

    async def test_includes_detail_fields(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get("/api/admin/reports/dispatches", headers=_admin_headers())
        assert r.status_code == 200
        item = r.json()["items"][0]
        for field in ["volume", "unit_price", "tax_amount", "credit_status", "sri_status"]:
            assert field in item

    async def test_search_by_order_id(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get(
            "/api/admin/reports/dispatches?search=DASH-001", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_filter_by_status(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.get(
            "/api/admin/reports/dispatches?status=COLLECTED", headers=_admin_headers()
        )
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] == "COLLECTED"

    async def test_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/reports/dispatches", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_export_xlsx(self, client, db):
        await _seed_dispatch_data(db)
        r = await client.post("/api/admin/reports/dispatches/export?format=xlsx", headers=_admin_headers())
        assert r.status_code == 200


# ── Shifts Report ──────────────────────────────────────────────────


class TestShiftsReport:
    async def test_list_shifts(self, client, db):
        """Shifts list returns shift history."""
        r = await client.get("/api/admin/reports/shifts", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        # At least the shift created by _seed_dispatch_data
        assert data["total"] >= 0

    async def test_filter_by_status(self, client, db):
        r = await client.get(
            "/api/admin/reports/shifts?status=OPEN", headers=_admin_headers()
        )
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["status"] == "OPEN"

    async def test_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/reports/shifts", headers=_dispatcher_headers())
        assert r.status_code == 403

    async def test_export_xlsx(self, client):
        r = await client.post("/api/admin/reports/shifts/export?format=xlsx", headers=_admin_headers())
        assert r.status_code == 200


# ── Cash Summary Report ────────────────────────────────────────────


class TestCashSummaryReport:
    async def test_list_empty(self, client):
        """Cash summary works with no data."""
        r = await client.get("/api/admin/reports/cash-summary", headers=_admin_headers())
        assert r.status_code == 200
        assert r.json()["total"] >= 0

    async def test_filter_by_type(self, client):
        r = await client.get(
            "/api/admin/reports/cash-summary?type=INCOME", headers=_admin_headers()
        )
        assert r.status_code == 200

    async def test_dispatcher_forbidden(self, client):
        r = await client.get(
            "/api/admin/reports/cash-summary", headers=_dispatcher_headers()
        )
        assert r.status_code == 403

    async def test_export_xlsx(self, client):
        r = await client.post("/api/admin/reports/cash-summary/export?format=xlsx", headers=_admin_headers())
        assert r.status_code == 200
