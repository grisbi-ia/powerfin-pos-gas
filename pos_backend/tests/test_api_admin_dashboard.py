"""Integration tests for admin dashboard endpoints."""

from decimal import Decimal

import pytest


def _admin_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(1, "admin", expire_minutes=240)
    return {"Authorization": f"Bearer {token}"}


def _dispatcher_headers():
    from app.services.auth_service import create_access_token
    token = create_access_token(2, "carlos")
    return {"Authorization": f"Bearer {token}"}


# ── Helpers ────────────────────────────────────────────────────────


async def _seed_dispatch_data(db):
    """Insert test dispatch data for dashboard aggregation."""
    from datetime import datetime
    from app.models.dispatch import Dispatch, DispatchDetail, DispatchPayment
    from app.models.shift import Shift
    from app.config import ECUADOR_TZ

    now = datetime.now(ECUADOR_TZ)

    # Create a shift for the dispatches
    shift = Shift(user_id=2, opening_cash=100.0, status="OPEN")
    db.add(shift)
    await db.flush()

    # Create 3 collected dispatches
    d1 = Dispatch(
        order_id="DASH-001", shift_id=shift.shift_id, dispenser_id=1, hose_id=1,
        dispatch_type_id=1, grade_id="DIESEL", status="COLLECTED",
        person_id=1, total=50.00, subtotal=43.48, tax_amount=6.52,
        created_at=now, authorized_by_user_id=2,
    )
    d2 = Dispatch(
        order_id="DASH-002", shift_id=shift.shift_id, dispenser_id=1, hose_id=1,
        dispatch_type_id=1, grade_id="DIESEL", status="COLLECTED",
        person_id=1, total=30.00, subtotal=26.09, tax_amount=3.91,
        created_at=now, authorized_by_user_id=2,
    )
    d3 = Dispatch(
        order_id="DASH-003", shift_id=shift.shift_id, dispenser_id=1, hose_id=1,
        dispatch_type_id=1, grade_id="SUPER", status="COLLECTED",
        person_id=2, total=45.00, subtotal=39.13, tax_amount=5.87,
        created_at=now, authorized_by_user_id=2,
    )
    db.add_all([d1, d2, d3])
    await db.flush()

    # Details
    db.add_all([
        DispatchDetail(dispatch_id=d1.dispatch_id, product_id=1, quantity=15.5,
                       unit_price=3.103, total=48.10, tax_rate=0.15, tax_amount=6.27,
                       price_without_subsidy=3.103, subsidy_amount=7.75),
        DispatchDetail(dispatch_id=d2.dispatch_id, product_id=1, quantity=10.0,
                       unit_price=3.103, total=31.03, tax_rate=0.15, tax_amount=4.05,
                       price_without_subsidy=3.103, subsidy_amount=5.00),
        DispatchDetail(dispatch_id=d3.dispatch_id, product_id=2, quantity=10.0,
                       unit_price=4.50, total=45.00, tax_rate=0.15, tax_amount=5.87,
                       price_without_subsidy=4.50, subsidy_amount=0),
    ])
    await db.flush()

    # Payments
    db.add_all([
        DispatchPayment(dispatch_id=d1.dispatch_id, payment_method_id=1, amount=50.00),
        DispatchPayment(dispatch_id=d2.dispatch_id, payment_method_id=2, amount=30.00),
        DispatchPayment(dispatch_id=d3.dispatch_id, payment_method_id=1, amount=20.00),
        DispatchPayment(dispatch_id=d3.dispatch_id, payment_method_id=2, amount=25.00),
    ])

    await db.commit()
    return d1, d2, d3


# ── Summary ────────────────────────────────────────────────────────


class TestDashboardSummary:
    async def test_summary_with_data(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get("/api/admin/dashboard/summary", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total_sales"] == 125.00  # 50+30+45
        assert data["dispatch_count"] == 3
        assert data["avg_ticket"] == 41.67  # 125/3
        assert data["cash_collected"] == 70.00  # d1(50) + d3(20)
        assert data["non_cash_collected"] == 55.00  # d2(30) + d3(25)
        # active_shifts depends on test state, just check it's present
        assert "active_shifts" in data

    async def test_summary_empty(self, client):
        """Dashboard works with no data (zeros, no error)."""
        r = await client.get("/api/admin/dashboard/summary", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert data["total_sales"] == 0
        assert data["dispatch_count"] == 0

    async def test_summary_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/dashboard/summary", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Sales by Day ───────────────────────────────────────────────────


class TestSalesByDay:
    async def test_sales_by_day(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get("/api/admin/dashboard/sales-by-day", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        today = data[0]
        assert today["total"] == 125.00
        assert today["count"] == 3

    async def test_sales_by_day_dispatcher_forbidden(self, client):
        r = await client.get("/api/admin/dashboard/sales-by-day", headers=_dispatcher_headers())
        assert r.status_code == 403


# ── Sales by Product ───────────────────────────────────────────────


class TestSalesByProduct:
    async def test_sales_by_product(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get("/api/admin/dashboard/sales-by-product", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2  # DIESEL, SUPER

        diesel = [p for p in data if p["product_code"] == "DIESEL"][0]
        assert diesel["total_liters"] == 25.5  # 15.5+10.0
        assert diesel["count"] == 2

        super_ = [p for p in data if p["product_code"] == "SUPER"][0]
        assert super_["total_liters"] == 10.0
        assert super_["count"] == 1


# ── Sales by Payment ───────────────────────────────────────────────


class TestSalesByPayment:
    async def test_sales_by_payment(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get("/api/admin/dashboard/sales-by-payment", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()

        efectivo = [p for p in data if p["method_code"] == "EFECTIVO"][0]
        assert efectivo["total"] == 70.00

        tarjeta = [p for p in data if p["method_code"] == "TARJETA"][0]
        assert tarjeta["total"] == 55.00


# ── Top Customers ──────────────────────────────────────────────────


class TestTopCustomers:
    async def test_top_customers(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get("/api/admin/dashboard/top-customers", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2  # person 1 + person 2
        top = data[0]  # person 1 with 50+30 = 80
        assert top["total"] == 80.00
        assert top["count"] == 2

    async def test_top_customers_limit(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get(
            "/api/admin/dashboard/top-customers?limit=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert len(r.json()) == 1


# ── Top Products ───────────────────────────────────────────────────


class TestTopProducts:
    async def test_top_products(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get("/api/admin/dashboard/top-products", headers=_admin_headers())
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        top = data[0]  # DIESEL with 25.5 liters
        assert top["product_code"] == "DIESEL"
        assert top["total_liters"] == 25.5

    async def test_top_products_limit(self, client, db):
        await _seed_dispatch_data(db)

        r = await client.get(
            "/api/admin/dashboard/top-products?limit=1", headers=_admin_headers()
        )
        assert r.status_code == 200
        assert len(r.json()) == 1
