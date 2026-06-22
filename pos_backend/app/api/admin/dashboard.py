"""Admin dashboard — summary KPI cards and chart data.

All endpoints accept date_from/date_to filters (default: current month).
Permissions: require_permission("dashboard", "read").
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.dispatch import Dispatch, DispatchDetail
from app.models.payment import PaymentMethod
from app.models.person import Person
from app.models.product import Product
from app.models.shift import Shift
from app.models.user import User
from app.schemas import (
    DashboardSummary,
    SalesByDayItem,
    SalesByPaymentItem,
    SalesByProductItem,
    TopCustomerItem,
    TopProductItem,
)

router = APIRouter(
    prefix="/api/admin/dashboard",
    tags=["admin-dashboard"],
    dependencies=[Depends(get_admin_user)],
)


def _default_date_range():
    """Default to current month."""
    today = date.today()
    return today.replace(day=1), today


# ── Summary ────────────────────────────────────────────────────────


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    date_from: date = Query(default=None, description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(default=None, description="End date (YYYY-MM-DD, inclusive)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """KPI cards: total sales, dispatch count, average ticket, cash breakdown."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    # Total sales and dispatch count (collected, non-cancelled)
    sales_row = (await db.execute(
        select(
            func.coalesce(func.sum(Dispatch.total), 0),
            func.count(Dispatch.dispatch_id),
        ).where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        )
    )).one()
    total_sales = float(sales_row[0] or 0)
    dispatch_count = int(sales_row[1] or 0)
    avg_ticket = round(total_sales / dispatch_count, 2) if dispatch_count > 0 else 0

    # Cash vs non-cash collected (join dispatch_payments)
    from app.models.dispatch import DispatchPayment
    cash = (await db.execute(
        select(func.coalesce(func.sum(DispatchPayment.amount), 0))
        .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.status == "COLLECTED",
            DispatchPayment.payment_method_id == 1,  # EFECTIVO
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        )
    )).scalar() or 0
    non_cash = total_sales - float(cash)

    # Active shifts now
    active_shifts = (await db.execute(
        select(func.count()).where(Shift.status == "OPEN")
    )).scalar() or 0

    return DashboardSummary(
        total_sales=round(total_sales, 2),
        dispatch_count=dispatch_count,
        avg_ticket=avg_ticket,
        cash_collected=round(float(cash), 2),
        non_cash_collected=round(non_cash, 2),
        active_shifts=active_shifts,
        date_from=date_from,
        date_to=date_to,
    )


# ── Sales by Day ───────────────────────────────────────────────────


@router.get("/sales-by-day", response_model=list[SalesByDayItem])
async def sales_by_day(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Daily sales totals for line chart."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    rows = (await db.execute(
        select(
            func.date(Dispatch.created_at).label("day"),
            func.coalesce(func.sum(Dispatch.total), 0).label("total"),
            func.count(Dispatch.dispatch_id).label("count"),
        ).where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(text("day")).order_by(text("day"))
    )).all()

    return [
        SalesByDayItem(date=row[0], total=round(float(row[1]), 2), count=int(row[2]))
        for row in rows
    ]


# ── Sales by Product ───────────────────────────────────────────────


@router.get("/sales-by-product", response_model=list[SalesByProductItem])
async def sales_by_product(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Sales breakdown by product (donut chart)."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    rows = (await db.execute(
        select(
            Product.name,
            Product.code,
            func.coalesce(func.sum(DispatchDetail.total), 0).label("total_amount"),
            func.coalesce(func.sum(DispatchDetail.quantity), 0).label("total_liters"),
            func.count(func.distinct(DispatchDetail.dispatch_id)).label("count"),
        ).select_from(DispatchDetail)
        .join(Dispatch, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .join(Product, DispatchDetail.product_id == Product.product_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(Product.name, Product.code)
        .order_by(text("total_amount DESC"))
    )).all()

    return [
        SalesByProductItem(
            product_name=row[0], product_code=row[1],
            total_amount=round(float(row[2]), 2),
            total_liters=round(float(row[3]), 2),
            count=int(row[4]),
        )
        for row in rows
    ]


# ── Sales by Payment ───────────────────────────────────────────────


@router.get("/sales-by-payment", response_model=list[SalesByPaymentItem])
async def sales_by_payment(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Sales breakdown by payment method (pie chart)."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    from app.models.dispatch import DispatchPayment
    rows = (await db.execute(
        select(
            PaymentMethod.name,
            PaymentMethod.code,
            func.coalesce(func.sum(DispatchPayment.amount), 0).label("total"),
            func.count(func.distinct(DispatchPayment.dispatch_id)).label("count"),
        ).select_from(DispatchPayment)
        .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
        .join(PaymentMethod, DispatchPayment.payment_method_id == PaymentMethod.payment_method_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(PaymentMethod.name, PaymentMethod.code)
        .order_by(text("total DESC"))
    )).all()

    return [
        SalesByPaymentItem(
            method_name=row[0], method_code=row[1],
            total=round(float(row[2]), 2), count=int(row[3]),
        )
        for row in rows
    ]


# ── Top Customers ──────────────────────────────────────────────────


@router.get("/top-customers", response_model=list[TopCustomerItem])
async def top_customers(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Top customers by total purchase amount (bar chart)."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    rows = (await db.execute(
        select(
            Person.person_id,
            Person.name,
            Person.id_number,
            func.coalesce(func.sum(Dispatch.total), 0).label("total"),
            func.count(Dispatch.dispatch_id).label("count"),
        ).select_from(Dispatch)
        .join(Person, Dispatch.person_id == Person.person_id)
        .where(
            Dispatch.status == "COLLECTED",
            Dispatch.person_id.isnot(None),
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(Person.person_id, Person.name, Person.id_number)
        .order_by(text("total DESC"))
        .limit(limit)
    )).all()

    return [
        TopCustomerItem(
            person_id=int(row[0]) if row[0] else None,
            customer_name=row[1] or "???",
            id_number=row[2],
            total=round(float(row[3]), 2),
            count=int(row[4]),
        )
        for row in rows
    ]


# ── Top Products ───────────────────────────────────────────────────


@router.get("/top-products", response_model=list[TopProductItem])
async def top_products(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Top products by volume (bar chart)."""
    if date_from is None or date_to is None:
        date_from, date_to = _default_date_range()

    rows = (await db.execute(
        select(
            Product.name,
            Product.code,
            func.coalesce(func.sum(DispatchDetail.total), 0).label("total_amount"),
            func.coalesce(func.sum(DispatchDetail.quantity), 0).label("total_liters"),
            func.count(func.distinct(DispatchDetail.dispatch_id)).label("count"),
        ).select_from(DispatchDetail)
        .join(Dispatch, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .join(Product, DispatchDetail.product_id == Product.product_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(Product.name, Product.code)
        .order_by(text("total_liters DESC"))
        .limit(limit)
    )).all()

    return [
        TopProductItem(
            product_name=row[0], product_code=row[1],
            total_amount=round(float(row[2]), 2),
            total_liters=round(float(row[3]), 2),
            count=int(row[4]),
        )
        for row in rows
    ]
