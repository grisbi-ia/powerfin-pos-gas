"""Admin dashboard — summary KPI cards and chart data.

All endpoints accept date_from/date_to filters (default: current month)
OR period + date for convenience (period=daily|monthly|annual).
Permissions: require_permission("dashboard", "read").
"""

import calendar
from datetime import date, datetime, timedelta
from enum import Enum

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
    CompareResponse,
    DashboardSummary,
    EvolutionCompareResponse,
    EvolutionItem,
    GallonsByPeriodItem,
    SalesByDayItem,
    SalesByPaymentItem,
    SalesByProductItem,
    TopCustomerItem,
    TopPeriodItem,
    TopProductItem,
)


class Period(str, Enum):
    daily = "daily"
    monthly = "monthly"
    annual = "annual"


router = APIRouter(
    prefix="/api/admin/dashboard",
    tags=["admin-dashboard"],
    dependencies=[Depends(get_admin_user)],
)


def _default_date_range():
    """Default to current month."""
    today = date.today()
    return today.replace(day=1), today


def _resolve_date_range(
    period: Period | None = None,
    date_val: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[date, date]:
    """Compute date_from/date_to from period+date, or use explicit range.

    Priority:
    1. If date_from and date_to are explicitly provided, use them (backward compat).
    2. If period and date_val are provided, compute the range.
    3. Otherwise, default to current month.
    """
    if date_from is not None and date_to is not None:
        return date_from, date_to

    if period is not None and date_val is not None:
        if period == Period.daily:
            return date_val, date_val
        elif period == Period.monthly:
            last_day = calendar.monthrange(date_val.year, date_val.month)[1]
            return date_val.replace(day=1), date_val.replace(day=last_day)
        elif period == Period.annual:
            return date_val.replace(month=1, day=1), date_val.replace(month=12, day=31)

    return _default_date_range()


# ── Summary ────────────────────────────────────────────────────────


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    date_from: date = Query(default=None, description="Start date (YYYY-MM-DD)"),
    date_to: date = Query(default=None, description="End date (YYYY-MM-DD, inclusive)"),
    period: Period = Query(default=None, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date for period"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """KPI cards: total sales, total gallons, dispatch count, avg ticket, cash breakdown."""
    date_from, date_to = _resolve_date_range(period, date_val, date_from, date_to)

    # Total sales, gallons, and dispatch count (collected, non-cancelled)
    from app.models.dispatch import DispatchPayment
    sales_row = (await db.execute(
        select(
            func.coalesce(func.sum(Dispatch.total), 0),
            func.coalesce(func.sum(DispatchDetail.quantity), 0),
            func.count(Dispatch.dispatch_id),
        ).outerjoin(DispatchDetail, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        )
    )).one()
    total_sales = float(sales_row[0] or 0)
    total_gallons = round(float(sales_row[1] or 0), 2)
    dispatch_count = int(sales_row[2] or 0)
    avg_ticket = round(total_sales / dispatch_count, 2) if dispatch_count > 0 else 0

    # Cash vs non-cash collected (join dispatch_payments)
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
        total_gallons=total_gallons,
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
    period: Period = Query(default=None, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date for period"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Sales time series — GROUP BY adapts to period.

    daily   → by hour   (24 buckets for a single day)
    monthly → by day    (28-31 buckets, current behavior)
    annual  → by month  (12 buckets)
    """
    date_from, date_to = _resolve_date_range(period, date_val, date_from, date_to)

    if period == Period.daily:
        bucket_label = func.extract("hour", Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")
    elif period == Period.annual:
        bucket_label = func.extract("month", Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")
    else:
        # monthly (default) → by day
        bucket_label = func.date(Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")

    rows = (await db.execute(
        select(
            bucket_label,
            func.coalesce(func.sum(Dispatch.total), 0).label("total"),
            func.coalesce(func.sum(DispatchDetail.quantity), 0).label("total_gallons"),
            func.count(Dispatch.dispatch_id).label("count"),
        ).outerjoin(DispatchDetail, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(text("bucket")).order_by(bucket_order)
    )).all()

    result = []
    for row in rows:
        if period == Period.daily:
            key = f"{date_val}T{int(row[0]):02d}:00" if date_val else f"Hour {int(row[0])}"
        elif period == Period.annual:
            key = date(date_val.year if date_val else date.today().year, int(row[0]), 1)
        else:
            key = row[0]
        result.append(SalesByDayItem(
            date=key,
            total=round(float(row[1]), 2),
            total_gallons=round(float(row[2]), 2),
            count=int(row[3]),
        ))
    return result


@router.get("/sales-by-day-product", response_model=list)
async def sales_by_day_product(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    period: Period = Query(default=None, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date for period"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Sales by day AND product for multi-line chart."""
    date_from, date_to = _resolve_date_range(period, date_val, date_from, date_to)

    rows = (await db.execute(
        select(
            func.date(Dispatch.created_at).label("day"),
            Product.name.label("product_name"),
            Product.code.label("product_code"),
            func.coalesce(func.sum(DispatchDetail.total), 0).label("total"),
        ).select_from(DispatchDetail)
        .join(Dispatch, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .join(Product, DispatchDetail.product_id == Product.product_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(text("day"), Product.name, Product.code)
        .order_by(text("day"), Product.name)
    )).all()

    result = []
    for row in rows:
        result.append({
            "date": str(row[0]),
            "product_name": row[1],
            "product_code": row[2],
            "total": round(float(row[3]), 2),
        })
    return result


# ── Sales by Product ───────────────────────────────────────────────


@router.get("/sales-by-hour", response_model=list)
async def sales_by_hour(
    date: date = Query(default=None, description="Date to query (defaults to today)"),
    period: Period = Query(default=None, description="If daily, queries by hour"),
    date_val: date = Query(default=None, alias="date_param", description="Date from period mode"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Sales grouped by hour for a given day (bar chart)."""
    if period and date_val:
        date = date_val
    if date is None:
        date = date.today()

    rows = (await db.execute(
        select(
            func.extract("hour", Dispatch.created_at).label("hour"),
            func.coalesce(func.sum(Dispatch.total), 0).label("total"),
            func.count(Dispatch.dispatch_id).label("count"),
        ).where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) == date,
        ).group_by(text("hour")).order_by(text("hour"))
    )).all()

    return [
        {"hour": int(row[0]), "total": round(float(row[1]), 2), "count": int(row[2])}
        for row in rows
    ]


@router.get("/sales-by-product", response_model=list[SalesByProductItem])
async def sales_by_product(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    period: Period = Query(default=None, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date for period"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Sales breakdown by product (donut chart)."""
    date_from, date_to = _resolve_date_range(period, date_val, date_from, date_to)

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
    period: Period = Query(default=None, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date for period"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Sales breakdown by payment method (pie chart)."""
    date_from, date_to = _resolve_date_range(period, date_val, date_from, date_to)

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
    period: Period = Query(default=None, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date for period"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Top customers by total purchase amount (bar chart)."""
    date_from, date_to = _resolve_date_range(period, date_val, date_from, date_to)

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
    period: Period = Query(default=None, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date for period"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Top products by volume (bar chart)."""
    date_from, date_to = _resolve_date_range(period, date_val, date_from, date_to)

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


# ── Evolution (time series with sales + gallons) ──────────────────


async def _compute_evolution(
    db: AsyncSession,
    period: Period,
    date_val: date,
) -> tuple[list[EvolutionItem], str]:
    """Compute evolution data for a given period+date.

    Returns (items, label) where label describes the period.
    """
    date_from, date_to = _resolve_date_range(period, date_val)

    if period == Period.daily:
        bucket_label = func.extract("hour", Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")
    elif period == Period.annual:
        bucket_label = func.extract("month", Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")
    else:
        bucket_label = func.date(Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")

    rows = (await db.execute(
        select(
            bucket_label,
            func.coalesce(func.sum(Dispatch.total), 0).label("sales"),
            func.coalesce(func.sum(DispatchDetail.quantity), 0).label("gallons"),
            func.count(Dispatch.dispatch_id).label("count"),
        ).outerjoin(DispatchDetail, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(text("bucket")).order_by(bucket_order)
    )).all()

    items = []
    for row in rows:
        if period == Period.daily:
            label = f"{date_val.isoformat()}T{int(row[0]):02d}:00"
        elif period == Period.annual:
            label = str(int(row[0])).zfill(2)  # "01".."12"
        else:
            label = str(row[0])
        items.append(EvolutionItem(
            period_label=label,
            sales=round(float(row[1]), 2),
            gallons=round(float(row[2]), 2),
            count=int(row[3]),
        ))

    if period == Period.daily:
        period_label = date_val.isoformat()
    elif period == Period.annual:
        period_label = str(date_val.year)
    else:
        period_label = date_val.strftime("%Y-%m")

    return items, period_label


def _shift_period(period: Period, date_val: date, direction: int) -> date:
    """Shift a date by one period unit (day/month/year).

    direction: -1 = previous, +1 = next
    """
    if period == Period.daily:
        return date_val + timedelta(days=direction)
    elif period == Period.monthly:
        m = date_val.month + direction
        y = date_val.year
        if m < 1:
            y -= 1; m = 12
        elif m > 12:
            y += 1; m = 1
        return date_val.replace(year=y, month=m, day=1)
    else:  # annual
        return date_val.replace(year=date_val.year + direction, month=1, day=1)


@router.get("/evolution", response_model=list[EvolutionItem])
async def evolution(
    period: Period = Query(default=Period.monthly, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Time series with sales + gallons.

    daily   → 24 hourly buckets
    monthly → 28-31 daily buckets
    annual  → 12 monthly buckets
    """
    if date_val is None:
        date_val = date.today()
    items, _ = await _compute_evolution(db, period, date_val)
    return items


@router.get("/evolution/compare", response_model=EvolutionCompareResponse)
async def evolution_compare(
    period: Period = Query(default=Period.daily, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Three-period evolution data for comparison charts.

    Returns previous, current, and next period side by side.
    Each dataset has the same number of buckets, aligned by position.
    """
    if date_val is None:
        date_val = date.today()

    prev_date = _shift_period(period, date_val, -1)
    next_date = _shift_period(period, date_val, +1)

    prev_items, prev_label = await _compute_evolution(db, period, prev_date)
    cur_items, cur_label = await _compute_evolution(db, period, date_val)
    next_items, next_label = await _compute_evolution(db, period, next_date)

    return EvolutionCompareResponse(
        period=period.value,
        current_label=cur_label,
        previous_label=prev_label,
        next_label=next_label,
        previous=prev_items,
        current=cur_items,
        next=next_items,
    )


# ── Compare (current vs previous period) ──────────────────────────


@router.get("/compare", response_model=CompareResponse)
async def compare_periods(
    period: Period = Query(default=Period.daily, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Compare current period KPI vs previous period.

    daily   → today vs yesterday
    monthly → this month vs last month
    annual  → this year vs last year
    """
    if date_val is None:
        date_val = date.today()

    # Current period
    cur_from, cur_to = _resolve_date_range(period, date_val)
    current = await _compute_summary(db, cur_from, cur_to)

    # Previous period (shift back by 1)
    if period == Period.daily:
        prev_date = date_val - timedelta(days=1)
    elif period == Period.monthly:
        if date_val.month == 1:
            prev_date = date_val.replace(year=date_val.year - 1, month=12, day=1)
        else:
            prev_date = date_val.replace(month=date_val.month - 1, day=1)
    else:  # annual
        prev_date = date_val.replace(year=date_val.year - 1, month=1, day=1)

    prev_from, prev_to = _resolve_date_range(period, prev_date)
    previous = await _compute_summary(db, prev_from, prev_to)

    # Growth percentages
    growth_sales = None
    growth_gallons = None
    if previous.total_sales > 0:
        growth_sales = round(
            ((current.total_sales - previous.total_sales) / previous.total_sales) * 100, 1
        )
    if previous.total_gallons > 0:
        growth_gallons = round(
            ((current.total_gallons - previous.total_gallons) / previous.total_gallons) * 100, 1
        )

    return CompareResponse(
        current=current,
        previous=previous,
        growth_sales_pct=growth_sales,
        growth_gallons_pct=growth_gallons,
    )


async def _compute_summary(
    db: AsyncSession, date_from: date, date_to: date
) -> DashboardSummary:
    """Shared summary computation for compare endpoint."""
    from app.models.dispatch import DispatchPayment

    sales_row = (await db.execute(
        select(
            func.coalesce(func.sum(Dispatch.total), 0),
            func.coalesce(func.sum(DispatchDetail.quantity), 0),
            func.count(Dispatch.dispatch_id),
        ).outerjoin(DispatchDetail, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        )
    )).one()
    total_sales = float(sales_row[0] or 0)
    total_gallons = round(float(sales_row[1] or 0), 2)
    dispatch_count = int(sales_row[2] or 0)
    avg_ticket = round(total_sales / dispatch_count, 2) if dispatch_count > 0 else 0

    cash = (await db.execute(
        select(func.coalesce(func.sum(DispatchPayment.amount), 0))
        .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.status == "COLLECTED",
            DispatchPayment.payment_method_id == 1,
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        )
    )).scalar() or 0
    non_cash = total_sales - float(cash)

    active_shifts = (await db.execute(
        select(func.count()).where(Shift.status == "OPEN")
    )).scalar() or 0

    return DashboardSummary(
        total_sales=round(total_sales, 2),
        total_gallons=total_gallons,
        dispatch_count=dispatch_count,
        avg_ticket=avg_ticket,
        cash_collected=round(float(cash), 2),
        non_cash_collected=round(non_cash, 2),
        active_shifts=active_shifts,
        date_from=date_from,
        date_to=date_to,
    )


# ── Top Periods (best days/months within a larger period) ─────────


@router.get("/top-periods", response_model=list[TopPeriodItem])
async def top_periods(
    period: Period = Query(default=Period.monthly, description="Parent period: monthly → top days, annual → top months"),
    date_val: date = Query(default=None, alias="date", description="Anchor date (defaults to today)"),
    limit: int = Query(5, ge=1, le=12, description="Number of results"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Best sub-periods ranked by sales.

    monthly → top N days of the month
    annual  → top N months of the year
    """
    if date_val is None:
        date_val = date.today()

    if period == Period.daily:
        # daily → no sub-periods, return empty
        return []

    date_from, date_to = _resolve_date_range(period, date_val)

    month_names_es = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]

    if period == Period.monthly:
        bucket_label = func.date(Dispatch.created_at).label("bucket")
        bucket_order = text("total_sales DESC")
    else:  # annual
        bucket_label = func.extract("month", Dispatch.created_at).label("bucket")
        bucket_order = text("total_sales DESC")

    rows = (await db.execute(
        select(
            bucket_label,
            func.coalesce(func.sum(Dispatch.total), 0).label("total_sales"),
            func.coalesce(func.sum(DispatchDetail.quantity), 0).label("total_gallons"),
            func.count(Dispatch.dispatch_id).label("count"),
        ).outerjoin(DispatchDetail, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(text("bucket")).order_by(bucket_order).limit(limit)
    )).all()

    result = []
    for row in rows:
        if period == Period.monthly:
            # Format: "26 Jun"
            d = row[0]
            if isinstance(d, date):
                label = f"{d.day} {month_names_es[d.month][:3]}"
            else:
                label = str(d)
        else:
            label = month_names_es[int(row[0])]
        result.append(TopPeriodItem(
            period_label=label,
            sales=round(float(row[1]), 2),
            gallons=round(float(row[2]), 2),
            count=int(row[3]),
        ))
    return result


# ── Gallons by Product (donut) ────────────────────────────────────


@router.get("/gallons-by-product", response_model=list[SalesByProductItem])
async def gallons_by_product(
    period: Period = Query(default=Period.monthly, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Gallons breakdown by product, sorted by volume (donut chart).

    Same data as sales-by-product but ranked by gallons instead of dollars.
    """
    if date_val is None:
        date_val = date.today()
    date_from, date_to = _resolve_date_range(period, date_val)

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


# ── Gallons by Period + Product (multi-line chart) ────────────────


@router.get("/gallons-by-period", response_model=list[GallonsByPeriodItem])
async def gallons_by_period(
    period: Period = Query(default=Period.daily, description="Period: daily, monthly, annual"),
    date_val: date = Query(default=None, alias="date", description="Anchor date (defaults to today)"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("dashboard", "read")),
):
    """Gallons time series broken down by product (multi-line chart).

    daily   → hourly buckets × product
    monthly → daily buckets × product
    annual  → monthly buckets × product
    """
    if date_val is None:
        date_val = date.today()
    date_from, date_to = _resolve_date_range(period, date_val)

    if period == Period.daily:
        bucket_label = func.extract("hour", Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")
    elif period == Period.annual:
        bucket_label = func.extract("month", Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")
    else:
        bucket_label = func.date(Dispatch.created_at).label("bucket")
        bucket_order = text("bucket")

    rows = (await db.execute(
        select(
            bucket_label,
            Product.product_id.label("product_id"),
            Product.name.label("product_name"),
            Product.code.label("product_code"),
            func.coalesce(func.sum(DispatchDetail.quantity), 0).label("gallons"),
            func.count(func.distinct(Dispatch.dispatch_id)).label("count"),
        ).select_from(DispatchDetail)
        .join(Dispatch, DispatchDetail.dispatch_id == Dispatch.dispatch_id)
        .join(Product, DispatchDetail.product_id == Product.product_id)
        .where(
            Dispatch.status == "COLLECTED",
            func.date(Dispatch.created_at) >= date_from,
            func.date(Dispatch.created_at) <= date_to,
        ).group_by(text("bucket"), Product.product_id, Product.name, Product.code)
        .order_by(bucket_order, Product.name)
    )).all()

    result = []
    for row in rows:
        if period == Period.daily:
            label = f"{date_val.isoformat()}T{int(row[0]):02d}:00"
        elif period == Period.annual:
            label = str(int(row[0])).zfill(2)
        else:
            label = str(row[0])
        result.append(GallonsByPeriodItem(
            period_label=label,
            product_id=int(row[1]),
            product_name=row[2],
            product_code=row[3],
            gallons=round(float(row[4]), 2),
            count=int(row[5]),
        ))
    return result
