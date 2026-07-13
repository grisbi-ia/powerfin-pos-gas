"""Admin reports — paginated sales, dispatches, shifts, cash-summary.

All endpoints are read-only GET with filters and pagination.
Permissions: require_permission("reports", "read").
"""

import math
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_admin_user, require_permission
from app.database import get_db
from app.models.company import SystemConfig
from app.models.dispatch import Dispatch, DispatchDetail, DispatchPayment
from app.models.dispenser import Dispenser, Hose
from app.models.payment import PaymentMethod
from app.models.person import Person, Vehicle
from app.models.shift import Shift
from app.models.user import User
from app.models import CashMovement
from app.models.company import CompanyInfo
from app.services.export_service import (
    generate_excel, generate_pdf,
    generate_shift_receipt_pdf, generate_shift_transactions_excel,
)
from app.schemas import (
    PaginatedResponse,
    ReportCashSummaryItem,
    ReportDispatchItem,
    ReportSalesItem,
    ReportShiftItem,
    CloseShiftResponse,
)

router = APIRouter(
    prefix="/api/admin/reports",
    tags=["admin-reports"],
    dependencies=[Depends(get_admin_user)],
)


# ── Helpers ────────────────────────────────────────────────────────


async def _build_sales_row(row, dispenser_map, pay_map, person_map, vehicle_map, hose_map, detail_map, user_map) -> dict:
    """Convert a Dispatch row to ReportSalesItem dict."""
    d = row[0] if isinstance(row, tuple) else row
    detail = detail_map.get(d.dispatch_id)
    return {
        "order_id": d.order_id,
        "date": d.created_at.isoformat() if d.created_at else None,
        "dispenser_name": dispenser_map.get(d.dispenser_id, f"#{d.dispenser_id}"),
        "hose_side": hose_map.get(d.hose_id, {}).get("side") if d.hose_id else None,
        "grade": d.grade_id,
        "customer_name": person_map.get(d.person_id, {}).get("name"),
        "id_number": person_map.get(d.person_id, {}).get("id_number"),
        "plate": vehicle_map.get(d.vehicle_id),
        "payment_method": pay_map.get(d.dispatch_id),
        "amount": float(d.total or 0),
        "volume": float(detail.quantity) if detail else None,
        "status": d.status,
        "sri_status": d.sri_status,
        "access_key": d.access_key,
        "authorized_by": user_map.get(d.authorized_by_user_id),
    }


async def _build_dispatch_row(row, dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map) -> dict:
    d = row[0] if isinstance(row, tuple) else row
    detail = detail_map.get(d.dispatch_id)
    return {
        "order_id": d.order_id,
        "date": d.created_at.isoformat() if d.created_at else None,
        "shift_id": d.shift_id,
        "dispenser_name": dispenser_map.get(d.dispenser_id, f"#{d.dispenser_id}"),
        "hose_side": hose_map.get(d.hose_id, {}).get("side") if d.hose_id else None,
        "grade": d.grade_id,
        "customer_name": person_map.get(d.person_id, {}).get("name"),
        "id_number": person_map.get(d.person_id, {}).get("id_number"),
        "plate": vehicle_map.get(d.vehicle_id),
        "payment_method": pay_map.get(d.dispatch_id),
        "amount": float(d.total or 0),
        "volume": float(detail.quantity) if detail else None,
        "unit_price": float(detail.unit_price) if detail else None,
        "tax_amount": float(detail.tax_amount) if detail else None,
        "status": d.status,
        "sri_status": d.sri_status,
        "access_key": d.access_key,
        "credit_status": d.credit_status,
        "authorized_by": None,
    }


async def _preload_maps(db, dispatches):
    """Preload dispenser, payment, person, vehicle, detail maps."""
    dispenser_ids = list({d.dispenser_id for d in dispatches})
    dispenser_map = {}
    if dispenser_ids:
        result = await db.execute(select(Dispenser).where(Dispenser.dispenser_id.in_(dispenser_ids)))
        for d in result.scalars():
            dispenser_map[d.dispenser_id] = d.name

    hose_ids = list({d.hose_id for d in dispatches if d.hose_id})
    hose_map = {}
    if hose_ids:
        result = await db.execute(select(Hose).where(Hose.hose_id.in_(hose_ids)))
        for h in result.scalars():
            hose_map[h.hose_id] = {"side": h.side}

    dispatch_ids = [d.dispatch_id for d in dispatches]
    pay_map = {}
    if dispatch_ids:
        result = await db.execute(
            select(DispatchPayment.dispatch_id, PaymentMethod.name)
            .join(PaymentMethod, DispatchPayment.payment_method_id == PaymentMethod.payment_method_id)
            .where(DispatchPayment.dispatch_id.in_(dispatch_ids))
        )
        for did, pname in result:
            pay_map[did] = pname

    person_ids = list({d.person_id for d in dispatches if d.person_id})
    person_map = {}
    if person_ids:
        result = await db.execute(select(Person).where(Person.person_id.in_(person_ids)))
        for p in result.scalars():
            person_map[p.person_id] = {"name": p.name, "id_number": p.id_number}

    vehicle_ids = list({d.vehicle_id for d in dispatches if d.vehicle_id})
    vehicle_map = {}
    if vehicle_ids:
        result = await db.execute(select(Vehicle).where(Vehicle.vehicle_id.in_(vehicle_ids)))
        for v in result.scalars():
            vehicle_map[v.vehicle_id] = v.plate

    detail_map = {}
    if dispatch_ids:
        result = await db.execute(
            select(DispatchDetail).where(DispatchDetail.dispatch_id.in_(dispatch_ids))
        )
        for det in result.scalars():
            detail_map[det.dispatch_id] = det

    user_ids = list({d.authorized_by_user_id for d in dispatches if d.authorized_by_user_id})
    user_map = {}
    if user_ids:
        result = await db.execute(select(User).where(User.user_id.in_(user_ids)))
        for u in result.scalars():
            user_map[u.user_id] = u.name

    return dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map, user_map


# ── Sales Report ────────────────────────────────────────────────────


@router.get("/sales", response_model=PaginatedResponse)
async def sales_report(
    date_from: date = Query(default=None, description="Start date"),
    date_to: date = Query(default=None, description="End date (inclusive)"),
    status: str = Query("COLLECTED", description="Dispatch status filter"),
    payment_method: str = Query("", description="Filter by payment method code"),
    search: str = Query("", description="Search by customer name or plate"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    """Paginated sales report with filters."""
    base = select(Dispatch).where(Dispatch.status == status)
    count_q = select(func.count(Dispatch.dispatch_id)).where(Dispatch.status == status)

    if date_from:
        base = base.where(func.date(Dispatch.created_at) >= date_from)
        count_q = count_q.where(func.date(Dispatch.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(Dispatch.created_at) <= date_to)
        count_q = count_q.where(func.date(Dispatch.created_at) <= date_to)

    if search:
        pattern = f"%{search.strip().lower()}%"
        # Join Person for name search
        base = base.outerjoin(Person, Dispatch.person_id == Person.person_id).where(
            func.lower(Person.name).like(pattern)
        )
        count_q = count_q.outerjoin(Person, Dispatch.person_id == Person.person_id).where(
            func.lower(Person.name).like(pattern)
        )

    if payment_method:
        pm_ids = (await db.execute(
            select(DispatchPayment.dispatch_id)
            .join(PaymentMethod, DispatchPayment.payment_method_id == PaymentMethod.payment_method_id)
            .where(PaymentMethod.code == payment_method.upper())
        )).scalars().all()
        if pm_ids:
            base = base.where(Dispatch.dispatch_id.in_(pm_ids))
            count_q = count_q.where(Dispatch.dispatch_id.in_(pm_ids))
        else:
            return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, pages=0)

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(Dispatch.created_at.desc()).offset(offset).limit(page_size)
    )
    dispatches = result.scalars().all()

    dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map, user_map = await _preload_maps(db, dispatches)

    items = [await _build_sales_row(d, dispenser_map, pay_map, person_map, vehicle_map, hose_map, detail_map, user_map) for d in dispatches]

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, pages=pages)


# ── Dispatches Report ───────────────────────────────────────────────


@router.get("/dispatches", response_model=PaginatedResponse)
async def dispatches_report(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    status: str = Query("", description="Status filter (empty = all non-cancelled)"),
    search: str = Query("", description="Search by customer name, plate, or order_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    """Detailed dispatch report with all fields."""
    base = select(Dispatch)
    count_q = select(func.count(Dispatch.dispatch_id))

    if status:
        base = base.where(Dispatch.status == status)
        count_q = count_q.where(Dispatch.status == status)
    else:
        base = base.where(Dispatch.status != "CANCELLED")
        count_q = count_q.where(Dispatch.status != "CANCELLED")

    if date_from:
        base = base.where(func.date(Dispatch.created_at) >= date_from)
        count_q = count_q.where(func.date(Dispatch.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(Dispatch.created_at) <= date_to)
        count_q = count_q.where(func.date(Dispatch.created_at) <= date_to)

    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        base = base.outerjoin(Person, Dispatch.person_id == Person.person_id).outerjoin(
            Vehicle, Dispatch.vehicle_id == Vehicle.vehicle_id
        ).where(or_(
            func.lower(Person.name).like(pattern),
            Vehicle.plate.ilike(pattern),
            Dispatch.order_id.ilike(pattern),
        ))
        count_q = count_q.outerjoin(Person, Dispatch.person_id == Person.person_id).outerjoin(
            Vehicle, Dispatch.vehicle_id == Vehicle.vehicle_id
        ).where(or_(
            func.lower(Person.name).like(pattern),
            Vehicle.plate.ilike(pattern),
            Dispatch.order_id.ilike(pattern),
        ))

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(Dispatch.created_at.desc()).offset(offset).limit(page_size)
    )
    dispatches = result.scalars().all()

    dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map, _ = await _preload_maps(db, dispatches)

    items = [
        await _build_dispatch_row(d, dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map)
        for d in dispatches
    ]

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, pages=pages)


# ── Shifts Report ───────────────────────────────────────────────────


@router.get("/shifts", response_model=PaginatedResponse)
async def shifts_report(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    closed_date_from: date = Query(default=None, description="Filter by closed date"),
    closed_date_to: date = Query(default=None, description="Filter by closed date"),
    status: str = Query("", description="OPEN, CLOSED, or empty for all"),
    search: str = Query("", description="Search by user name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    """Shift history with summary data."""
    base = select(Shift, User.name).join(User, Shift.user_id == User.user_id)
    count_q = select(func.count(Shift.shift_id)).join(User, Shift.user_id == User.user_id)

    if status:
        base = base.where(Shift.status == status)
        count_q = count_q.where(Shift.status == status)

    # Build date conditions: (opened today) OR (closed today)
    from sqlalchemy import or_, and_
    opened_conds = []
    closed_conds = []
    if date_from:
        opened_conds.append(func.date(Shift.opened_at) >= date_from)
    if date_to:
        opened_conds.append(func.date(Shift.opened_at) <= date_to)
    if closed_date_from:
        closed_conds.append(func.date(Shift.closed_at) >= closed_date_from)
    if closed_date_to:
        closed_conds.append(func.date(Shift.closed_at) <= closed_date_to)

    combined = []
    if opened_conds:
        combined.append(and_(*opened_conds))
    if closed_conds:
        combined.append(and_(*closed_conds))

    if len(combined) == 1:
        base = base.where(combined[0])
        count_q = count_q.where(combined[0])
    elif len(combined) > 1:
        base = base.where(or_(*combined))
        count_q = count_q.where(or_(*combined))

    if search:
        pattern = f"%{search.strip().lower()}%"
        base = base.where(func.lower(User.name).like(pattern))
        count_q = count_q.where(func.lower(User.name).like(pattern))

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(Shift.shift_id.desc()).offset(offset).limit(page_size)
    )
    rows = result.all()

    items = []
    for shift, user_name in rows:
        dispatch_count = (await db.execute(
            select(func.count()).where(
                Dispatch.shift_id == shift.shift_id, Dispatch.status != "CANCELLED"
            )
        )).scalar() or 0
        collected = (await db.execute(
            select(func.coalesce(func.sum(DispatchPayment.amount), 0))
            .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
            .where(Dispatch.shift_id == shift.shift_id, Dispatch.status == "COLLECTED")
        )).scalar() or 0
        collected_cash = (await db.execute(
            select(func.coalesce(func.sum(DispatchPayment.amount), 0))
            .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
            .where(Dispatch.shift_id == shift.shift_id, Dispatch.status == "COLLECTED",
                   DispatchPayment.payment_method_id == 1)
        )).scalar() or 0

        # ── Efectivo Actual = Apertura + Ventas Efectivo + Ingresos − Egresos − Depósitos − Transf − Safe Drops
        income = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type.in_(["INCOME", "TRANSFER_IN"]))
        )).scalar() or 0
        expense = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "EXPENSE")
        )).scalar() or 0
        deposits = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "DEPOSIT")
        )).scalar() or 0
        transfers_out = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "TRANSFER_OUT")
        )).scalar() or 0
        safe_drops = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "SAFE_DROP")
        )).scalar() or 0

        efectivo_actual = round(float(shift.opening_cash or 0) + float(collected_cash) + float(income) - float(expense) - float(deposits) - float(transfers_out) - float(safe_drops), 2)

        items.append(ReportShiftItem(
            shift_id=shift.shift_id,
            user_name=user_name,
            opened_at=shift.opened_at.isoformat() if shift.opened_at else None,
            closed_at=shift.closed_at.isoformat() if shift.closed_at else None,
            status=shift.status,
            opening_cash=float(shift.opening_cash or 0),
            collected=round(float(collected), 2),
            collected_cash=round(float(collected_cash), 2),
            efectivo_actual=efectivo_actual,
            surplus=round(float(shift.surplus or 0), 2),
            shortage=round(float(shift.shortage or 0), 2),
            dispatch_count=dispatch_count,
        ))

    return PaginatedResponse(items=[i.model_dump() for i in items], total=total,
                             page=page, page_size=page_size, pages=pages)


# ── Cash Summary Report ─────────────────────────────────────────────


@router.get("/cash-summary", response_model=PaginatedResponse)
async def cash_summary_report(
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    type: str = Query("", description="INCOME, EXPENSE, DEPOSIT, TRANSFER_OUT, TRANSFER_IN, SAFE_DROP"),
    search: str = Query("", description="Search by observation or user"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    """Consolidated cash movements with filters."""
    base = select(CashMovement, User.name, Shift.opened_at).join(
        Shift, CashMovement.shift_id == Shift.shift_id
    ).join(User, Shift.user_id == User.user_id)
    count_q = select(func.count(CashMovement.movement_id)).join(
        Shift, CashMovement.shift_id == Shift.shift_id
    ).join(User, Shift.user_id == User.user_id)

    if type:
        base = base.where(CashMovement.type == type)
        count_q = count_q.where(CashMovement.type == type)

    if date_from:
        base = base.where(func.date(CashMovement.created_at) >= date_from)
        count_q = count_q.where(func.date(CashMovement.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(CashMovement.created_at) <= date_to)
        count_q = count_q.where(func.date(CashMovement.created_at) <= date_to)

    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        base = base.where(or_(
            func.lower(CashMovement.observation).like(pattern),
            func.lower(User.name).like(pattern),
        ))
        count_q = count_q.where(or_(
            func.lower(CashMovement.observation).like(pattern),
            func.lower(User.name).like(pattern),
        ))

    total = (await db.execute(count_q)).scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(CashMovement.movement_id.desc()).offset(offset).limit(page_size)
    )
    rows = result.all()

    items = []
    for mv, user_name, _ in rows:
        items.append(ReportCashSummaryItem(
            shift_id=mv.shift_id,
            user_name=user_name,
            type=mv.type,
            amount=float(mv.amount or 0),
            observation=mv.observation,
            date=mv.created_at.isoformat() if mv.created_at else None,
            running_balance=float(mv.running_balance or 0),
        ))

    return PaginatedResponse(items=[i.model_dump() for i in items], total=total,
                             page=page, page_size=page_size, pages=pages)


# ── Export Endpoints ───────────────────────────────────────────────



async def _query_all_sales_export(db, date_from, date_to, status, search, payment_method):
    """Reuse sales query logic for export (no pagination)."""
    base = select(Dispatch).where(Dispatch.status == status)
    if date_from:
        base = base.where(func.date(Dispatch.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(Dispatch.created_at) <= date_to)
    if search:
        pattern = f"%{search.strip().lower()}%"
        base = base.outerjoin(Person, Dispatch.person_id == Person.person_id).where(
            func.lower(Person.name).like(pattern)
        )
    if payment_method:
        pm_ids = (await db.execute(
            select(DispatchPayment.dispatch_id)
            .join(PaymentMethod, DispatchPayment.payment_method_id == PaymentMethod.payment_method_id)
            .where(PaymentMethod.code == payment_method.upper())
        )).scalars().all()
        if pm_ids:
            base = base.where(Dispatch.dispatch_id.in_(pm_ids))
        else:
            return []
    result = await db.execute(base.order_by(Dispatch.created_at.desc()))
    return result.scalars().all()


@router.post("/sales/export")
async def export_sales(
    format: str = Query("xlsx", pattern=r"^(pdf|xlsx)$"),
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    status: str = Query("COLLECTED"),
    payment_method: str = Query(""),
    search: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    dispatches = await _query_all_sales_export(db, date_from, date_to, status, search, payment_method)
    dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map, user_map = await _preload_maps(db, dispatches)

    columns = ["Order ID", "Fecha", "Surtidor", "Grado", "Cliente", u"Cédula/RUC", "Placa", "Pago", "Monto", "Galones", "Estado", "SRI"]
    rows = []
    for d in dispatches:
        row = await _build_sales_row(d, dispenser_map, pay_map, person_map, vehicle_map, hose_map, detail_map, user_map)
        rows.append([
            row["order_id"], row["date"] or "", row["dispenser_name"] or "",
            row["grade"] or "", row["customer_name"] or "", row["id_number"] or "",
            row["plate"] or "", row["payment_method"] or "",
            f"${row['amount']:,.2f}",
            f"{row['volume']:.2f}" if row["volume"] else "",
            row["status"], row["sri_status"] or "",
        ])

    if format == "pdf":
        data = generate_pdf("Reporte de Ventas", columns, rows)
        media = "application/pdf"
        ext = "pdf"
    else:
        data = generate_excel("Reporte de Ventas", columns, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    return Response(content=data, media_type=media,
                            headers={"Content-Disposition": f"attachment; filename=ventas.{ext}"})


@router.post("/dispatches/export")
async def export_dispatches(
    format: str = Query("xlsx", pattern=r"^(pdf|xlsx)$"),
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    status: str = Query(""),
    search: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    base = select(Dispatch)
    if status:
        base = base.where(Dispatch.status == status)
    else:
        base = base.where(Dispatch.status != "CANCELLED")
    if date_from:
        base = base.where(func.date(Dispatch.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(Dispatch.created_at) <= date_to)
    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        base = base.outerjoin(Person, Dispatch.person_id == Person.person_id).outerjoin(
            Vehicle, Dispatch.vehicle_id == Vehicle.vehicle_id
        ).where(or_(
            func.lower(Person.name).like(pattern),
            Vehicle.plate.ilike(pattern),
            Dispatch.order_id.ilike(pattern),
        ))
    result = await db.execute(base.order_by(Dispatch.created_at.desc()))
    dispatches = result.scalars().all()
    dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map, _ = await _preload_maps(db, dispatches)

    columns = ["Order ID", "Fecha", "Turno", "Surtidor", "Lado", "Grado", "Cliente",
               "Placa", "Pago", "Monto", "Volumen", "Precio Unit", "IVA",
               "Estado", "SRI", u"Crédito"]
    rows = []
    for d in dispatches:
        row = await _build_dispatch_row(d, dispenser_map, hose_map, pay_map, person_map, vehicle_map, detail_map)
        rows.append([
            row["order_id"], row["date"] or "", str(row["shift_id"]),
            row["dispenser_name"] or "", row["hose_side"] or "", row["grade"] or "",
            row["customer_name"] or "", row["plate"] or "", row["payment_method"] or "",
            f"${row['amount']:,.2f}", f"{row['volume']:.2f}" if row["volume"] else "",
            f"${row['unit_price']:.4f}" if row["unit_price"] else "",
            f"${row['tax_amount']:.2f}" if row["tax_amount"] else "",
            row["status"], row["sri_status"] or "", row["credit_status"] or "",
        ])

    if format == "pdf":
        data = generate_pdf("Reporte de Despachos", columns, rows)
        media = "application/pdf"
        ext = "pdf"
    else:
        data = generate_excel("Reporte de Despachos", columns, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    return Response(content=data, media_type=media,
                            headers={"Content-Disposition": f"attachment; filename=despachos.{ext}"})


@router.post("/shifts/export")
async def export_shifts(
    format: str = Query("xlsx", pattern=r"^(pdf|xlsx)$"),
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    status: str = Query(""),
    search: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    base = select(Shift, User.name).join(User, Shift.user_id == User.user_id)
    if status:
        base = base.where(Shift.status == status)
    if date_from:
        base = base.where(func.date(Shift.opened_at) >= date_from)
    if date_to:
        base = base.where(func.date(Shift.opened_at) <= date_to)
    if search:
        pattern = f"%{search.strip().lower()}%"
        base = base.where(func.lower(User.name).like(pattern))
    result = await db.execute(base.order_by(Shift.shift_id.desc()))
    rows_raw = result.all()

    columns = ["Turno", "Usuario", "Apertura", "Cierre", "Estado",
               "Caja Inicial", "Cobrado Total", "Efectivo Ventas", "Efectivo Actual", "Sobrante", "Faltante", "Despachos"]
    rows = []
    for shift, user_name in rows_raw:
        dispatch_count = (await db.execute(
            select(func.count()).where(Dispatch.shift_id == shift.shift_id, Dispatch.status != "CANCELLED")
        )).scalar() or 0
        collected = (await db.execute(
            select(func.coalesce(func.sum(DispatchPayment.amount), 0))
            .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
            .where(Dispatch.shift_id == shift.shift_id, Dispatch.status == "COLLECTED")
        )).scalar() or 0
        collected_cash = (await db.execute(
            select(func.coalesce(func.sum(DispatchPayment.amount), 0))
            .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
            .where(Dispatch.shift_id == shift.shift_id, Dispatch.status == "COLLECTED",
                   DispatchPayment.payment_method_id == 1)
        )).scalar() or 0
        # Efectivo Actual
        income_exp = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type.in_(["INCOME", "TRANSFER_IN"]))
        )).scalar() or 0
        expense_exp = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "EXPENSE")
        )).scalar() or 0
        deposits_exp = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "DEPOSIT")
        )).scalar() or 0
        transfers_out_exp = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "TRANSFER_OUT")
        )).scalar() or 0
        safe_drops_exp = (await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0))
            .where(CashMovement.shift_id == shift.shift_id, CashMovement.type == "SAFE_DROP")
        )).scalar() or 0
        actual_exp = round(float(shift.opening_cash or 0) + float(collected_cash) + float(income_exp) - float(expense_exp) - float(deposits_exp) - float(transfers_out_exp) - float(safe_drops_exp), 2)
        rows.append([
            str(shift.shift_id), user_name,
            shift.opened_at.isoformat() if shift.opened_at else "",
            shift.closed_at.isoformat() if shift.closed_at else "",
            shift.status,
            f"${float(shift.opening_cash or 0):,.2f}",
            f"${float(collected):,.2f}",
            f"${float(collected_cash):,.2f}",
            f"${actual_exp:,.2f}",
            f"${float(shift.surplus or 0):,.2f}",
            f"${float(shift.shortage or 0):,.2f}",
            str(dispatch_count),
        ])

    if format == "pdf":
        data = generate_pdf("Reporte de Turnos", columns, rows)
        media = "application/pdf"
        ext = "pdf"
    else:
        data = generate_excel("Reporte de Turnos", columns, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    return Response(content=data, media_type=media,
                            headers={"Content-Disposition": f"attachment; filename=turnos.{ext}"})


@router.post("/cash-summary/export")
async def export_cash_summary(
    format: str = Query("xlsx", pattern=r"^(pdf|xlsx)$"),
    date_from: date = Query(default=None),
    date_to: date = Query(default=None),
    type: str = Query(""),
    search: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    base = select(CashMovement, User.name).join(
        Shift, CashMovement.shift_id == Shift.shift_id
    ).join(User, Shift.user_id == User.user_id)
    if type:
        base = base.where(CashMovement.type == type)
    if date_from:
        base = base.where(func.date(CashMovement.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(CashMovement.created_at) <= date_to)
    if search:
        pattern = f"%{search.strip().lower()}%"
        from sqlalchemy import or_
        base = base.where(or_(
            func.lower(CashMovement.observation).like(pattern),
            func.lower(User.name).like(pattern),
        ))
    result = await db.execute(base.order_by(CashMovement.movement_id.desc()))
    rows_raw = result.all()

    columns = ["Turno", "Usuario", "Tipo", "Monto", u"Observación", "Fecha", "Balance"]
    rows = []
    for mv, user_name in rows_raw:
        rows.append([
            str(mv.shift_id), user_name, mv.type,
            f"${float(mv.amount or 0):,.2f}", mv.observation or "",
            mv.created_at.isoformat() if mv.created_at else "",
            f"${float(mv.running_balance or 0):,.2f}",
        ])

    if format == "pdf":
        data = generate_pdf("Resumen de Caja", columns, rows)
        media = "application/pdf"
        ext = "pdf"
    else:
        data = generate_excel("Resumen de Caja", columns, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"
    return Response(content=data, media_type=media,
                            headers={"Content-Disposition": f"attachment; filename=caja.{ext}"})


# ── Per-Shift Actions ─────────────────────────────────────────────


@router.get("/shifts/{shift_id}/receipt")
async def shift_receipt_pdf(
    shift_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    """Generate shift close receipt PDF (same layout as thermal ticket)."""
    # Fetch shift
    result = await db.execute(select(Shift).where(Shift.shift_id == shift_id))
    shift = result.scalar_one_or_none()
    if not shift:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    if shift.status != "CLOSED":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="El turno aún no está cerrado")

    # Recompute financial summary
    from app.api.shifts import _compute_shift_summary
    summary = await _compute_shift_summary(db, shift_id)

    # Cashier name
    cashier = await db.scalar(
        select(User.name).where(User.user_id == shift.user_id)
    ) or ""

    # Company info
    company_name = company_ruc = company_address = company_phone = ""
    ci_result = await db.execute(select(CompanyInfo).limit(1))
    ci = ci_result.scalar_one_or_none()
    if ci:
        company_name = ci.commercial_name or ci.name or "NEOGAS"
        company_ruc = ci.ruc or ""
        company_address = ci.address or ""
        company_phone = ci.phone or ""

    surplus = float(shift.surplus or 0)
    shortage = float(shift.shortage or 0)
    total_sales = round(summary["sales_cash"] + sum(n["total"] for n in summary["non_cash_sales"]), 2)

    pdf_bytes = generate_shift_receipt_pdf(
        shift_id=shift_id,
        opened_at=shift.opened_at.strftime("%Y-%m-%d %H:%M") if shift.opened_at else "",
        closed_at=shift.closed_at.strftime("%Y-%m-%d %H:%M") if shift.closed_at else "",
        cashier=cashier,
        opening_cash=float(shift.opening_cash or 0),
        cash_income=round(summary["income"], 2),
        cash_income_count=summary["income_count"],
        cash_expense=round(summary["expense"], 2),
        cash_expense_count=summary["expense_count"],
        cash_deposits=round(summary["deposits"], 2),
        cash_deposits_count=summary["deposit_count"],
        cash_transfers_out=round(summary["transfers_out"], 2),
        cash_transfers_out_count=summary["transfer_out_count"],
        cash_transfers_in=round(summary["transfers_recv_amount"], 2),
        cash_transfers_in_count=summary["transfers_recv_count"],
        cash_safe_drops=round(summary["safe_drops"], 2),
        cash_safe_drops_count=summary["safe_drop_count"],
        sales_cash=round(summary["sales_cash"], 2),
        sales_cash_count=summary["sales_cash_count"],
        surplus=surplus,
        shortage=shortage,
        non_cash_sales=summary["non_cash_sales"],
        total_sales=total_sales,
        dispatch_count=summary["dispatch_count"],
        company_name=company_name,
        company_ruc=company_ruc,
        company_address=company_address,
        company_phone=company_phone,
        is_reprint=True,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=cierre_turno_{shift_id}.pdf"},
    )


@router.get("/shifts/{shift_id}/transactions/export")
async def shift_transactions_export(
    shift_id: int,
    format: str = Query("xlsx", pattern=r"^(xlsx)$"),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("reports", "read")),
):
    """Export shift transactions as Excel (dispatches + cash movements)."""
    # Verify shift exists
    result = await db.execute(select(Shift).where(Shift.shift_id == shift_id))
    shift = result.scalar_one_or_none()
    if not shift:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    # Company info
    company_name = "NEOGAS"
    ci_result = await db.execute(select(CompanyInfo).limit(1))
    ci = ci_result.scalar_one_or_none()
    if ci:
        company_name = ci.commercial_name or ci.name or "NEOGAS"

    # Fetch dispatches for this shift
    dispatch_rows = await db.execute(
        select(Dispatch)
        .where(Dispatch.shift_id == shift_id)
        .where(Dispatch.status != "CANCELLED")
        .order_by(Dispatch.created_at.asc())
    )
    dispatches = dispatch_rows.scalars().all()

    # Build lookup maps
    hose_ids = [d.hose_id for d in dispatches if d.hose_id]
    hose_map = {}
    if hose_ids:
        hr = await db.execute(select(Hose).where(Hose.hose_id.in_(hose_ids)))
        for h in hr.scalars():
            hose_map[h.hose_id] = h

    dispatch_ids = [d.dispatch_id for d in dispatches]
    detail_map = {}
    if dispatch_ids:
        dr = await db.execute(select(DispatchDetail).where(DispatchDetail.dispatch_id.in_(dispatch_ids)))
        for det in dr.scalars():
            detail_map[det.dispatch_id] = det

    person_ids = [d.person_id for d in dispatches if d.person_id]
    person_map = {}
    if person_ids:
        pr = await db.execute(select(Person).where(Person.person_id.in_(person_ids)))
        for p in pr.scalars():
            person_map[p.person_id] = p

    vehicle_ids = [d.vehicle_id for d in dispatches if d.vehicle_id]
    vehicle_map = {}
    if vehicle_ids:
        from app.models.person import Vehicle as VehicleModel
        vr = await db.execute(select(VehicleModel).where(VehicleModel.vehicle_id.in_(vehicle_ids)))
        for v in vr.scalars():
            vehicle_map[v.vehicle_id] = v

    pay_map = {}
    if dispatch_ids:
        pay_result = await db.execute(
            select(DispatchPayment.dispatch_id, PaymentMethod.name)
            .join(PaymentMethod, DispatchPayment.payment_method_id == PaymentMethod.payment_method_id)
            .where(DispatchPayment.dispatch_id.in_(dispatch_ids))
        )
        for did, pname in pay_result:
            pay_map[did] = pname

    # Format dispatches
    dispatch_data = []
    for d in dispatches:
        side = hose_map[d.hose_id].side if d.hose_id and d.hose_id in hose_map else "?"
        person = person_map.get(d.person_id)
        vehicle = vehicle_map.get(d.vehicle_id)
        detail = detail_map.get(d.dispatch_id)
        dispatch_data.append({
            "order_id": d.order_id,
            "dispenser_id": d.dispenser_id,
            "side": side,
            "grade": d.grade_id or "",
            "customer_name": person.name if person else None,
            "plate": vehicle.plate if vehicle else None,
            "payment_method_name": pay_map.get(d.dispatch_id, ""),
            "final_amount": float(d.total or 0),
            "final_volume": str(detail.quantity) if detail and detail.quantity else "0",
            "unit_price": float(detail.unit_price) if detail and detail.unit_price else 0,
            "subsidy_amount": float(detail.subsidy_amount) if detail and detail.subsidy_amount else 0,
            "status": d.status,
            "sri_status": d.sri_status,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        })

    # Fetch cash movements
    cm_result = await db.execute(
        select(CashMovement)
        .where(CashMovement.shift_id == shift_id)
        .order_by(CashMovement.movement_id.asc())
    )
    cash_movements = cm_result.scalars().all()

    cash_data = []
    for cm in cash_movements:
        cash_data.append({
            "movement_id": cm.movement_id,
            "type": cm.type,
            "amount": float(cm.amount or 0),
            "observation": cm.observation,
            "running_balance": float(cm.running_balance or 0),
            "related_user_name": cm.related_user_name,
            "created_at": cm.created_at.isoformat() if cm.created_at else "",
        })

    xlsx_bytes = generate_shift_transactions_excel(
        shift_id=shift_id,
        dispatches=dispatch_data,
        cash_movements=cash_data,
        company_name=company_name,
    )

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=transacciones_turno_{shift_id}.xlsx"},
    )

