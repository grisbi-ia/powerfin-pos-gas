"""Shift management — open, current, close."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import ECUADOR_TZ
from app.database import get_db
from app.models import CashMovement, Dispatch, Shift
from app.models.payment import PaymentMethod
from app.models.user import User
from app.schemas import (
    CloseShiftRequest,
    CloseShiftResponse,
    OpenShiftRequest,
    ShiftResponse,
)

router = APIRouter(prefix="/api/pos/shifts", tags=["shifts"])


@router.post("/open", response_model=ShiftResponse, status_code=201)
async def open_shift(
    body: OpenShiftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open a new shift for the authenticated user."""
    # Close any existing open shift for this user
    existing = await db.execute(
        select(Shift).where(
            Shift.user_id == current_user.user_id,
            Shift.status == "OPEN",
        )
    )
    for s in existing.scalars().all():
        s.status = "CLOSED"
        s.closed_at = datetime.now(ECUADOR_TZ)

    shift = Shift(
        user_id=current_user.user_id,
        opening_cash=float(body.opening_cash),
        status="OPEN",
    )
    db.add(shift)
    await db.commit()
    await db.refresh(shift)

    return ShiftResponse(
        shift_id=shift.shift_id,
        user_id=shift.user_id,
        user_name=body.user_name or current_user.name,
        opened_at=shift.opened_at,
        accounting_date=str(shift.accounting_date),
        status=shift.status,
        opening_cash=shift.opening_cash,
    )


@router.get("/current", response_model=ShiftResponse | None)
async def get_current_shift(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the currently open shift for the authenticated user."""
    result = await db.execute(
        select(Shift).where(
            Shift.user_id == current_user.user_id,
            Shift.status == "OPEN",
        )
    )
    shift = result.scalar_one_or_none()
    if not shift:
        return None

    return ShiftResponse(
        shift_id=shift.shift_id,
        user_id=shift.user_id,
        user_name=current_user.name,
        opened_at=shift.opened_at,
        accounting_date=str(shift.accounting_date),
        status=shift.status,
        opening_cash=shift.opening_cash,
    )


@router.post("/{shift_id}/close", response_model=CloseShiftResponse)
async def close_shift(
    shift_id: int,
    body: CloseShiftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close a shift with cash count and summary."""
    result = await db.execute(
        select(Shift).where(Shift.shift_id == shift_id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    shift.status = "CLOSED"
    shift.closed_at = datetime.now(ECUADOR_TZ)
    shift.closing_cash = float(body.closing_cash)

    # Count dispatches
    dispatch_count = await db.scalar(
        select(func.count()).where(
            Dispatch.shift_id == shift_id, Dispatch.status != "CANCELLED"
        )
    ) or 0

    # Sum sales by payment method
    cash_method = await db.execute(
        select(PaymentMethod).where(PaymentMethod.code == "EFECTIVO")
    )
    cash_method_id = cash_method.scalar_one_or_none()
    cash_method_id = cash_method_id.payment_method_id if cash_method_id else None

    # Sum sales paid in cash — all COLLECTED dispatches in this shift
    # (shift_id is updated to collector's shift at collection time)
    sales_cash = await db.scalar(
        select(func.coalesce(func.sum(Dispatch.total), 0)).where(
            Dispatch.shift_id == shift_id,
            Dispatch.status == "COLLECTED",
        )
    ) or 0.0

    # Cash movements — income, expense, transfers, safe drops
    income = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id,
            CashMovement.type == "INCOME",
        )
    ) or 0.0
    expense = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id,
            CashMovement.type == "EXPENSE",
        )
    ) or 0.0
    transfers_out = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id,
            CashMovement.type == "TRANSFER_OUT",
        )
    ) or 0.0
    safe_drops = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id,
            CashMovement.type == "SAFE_DROP",
        )
    ) or 0.0

    # Income already includes transfers received (created as INCOME for receiver)
    # Cast all to float — Numeric columns return Decimal from asyncpg
    expected = float(shift.opening_cash) + float(income) + float(sales_cash) - float(expense) - float(transfers_out) - float(safe_drops)
    diff = float(body.closing_cash) - expected

    # System config for branch code
    from app.models.company import SystemConfig
    branch_code = await db.scalar(
        select(SystemConfig.value).where(SystemConfig.key == "accounting_branch_code")
    )

    await db.commit()

    return CloseShiftResponse(
        shift_id=shift_id,
        closed_at=shift.closed_at,
        opening_cash=shift.opening_cash,
        closing_cash=body.closing_cash,
        expected_cash=round(expected, 2),
        difference=round(diff, 2),
        total_sales=dispatch_count,
        total_volume=0,
        dispatch_count=dispatch_count,
        accounting_cash_code=current_user.accounting_cash_code,
        accounting_branch_code=branch_code,
    )


@router.get("/{shift_id}/dispatches", response_model=list)
async def get_shift_dispatches(
    shift_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get all dispatches for a shift (used for multi-device reconciliation)."""
    from app.models.dispenser import Hose
    from app.models.dispatch import DispatchDetail
    
    result = await db.execute(
        select(Dispatch).where(Dispatch.shift_id == shift_id).order_by(Dispatch.created_at.desc())
    )
    dispatches = result.scalars().all()

    # Build hose lookup for side resolution
    hose_ids = [d.hose_id for d in dispatches if d.hose_id]
    hose_map = {}
    if hose_ids:
        hoses_result = await db.execute(select(Hose).where(Hose.hose_id.in_(hose_ids)))
        for h in hoses_result.scalars():
            hose_map[h.hose_id] = h

    # Build detail lookup for unit_price and quantity
    dispatch_ids = [d.dispatch_id for d in dispatches]
    detail_map = {}
    if dispatch_ids:
        details_result = await db.execute(
            select(DispatchDetail).where(DispatchDetail.dispatch_id.in_(dispatch_ids))
        )
        for det in details_result.scalars():
            detail_map[det.dispatch_id] = det

    # Build person lookup for customer info
    person_ids = [d.person_id for d in dispatches if d.person_id]
    person_map = {}
    if person_ids:
        from app.models import Person as PersonModel
        persons_result = await db.execute(
            select(PersonModel).where(PersonModel.person_id.in_(person_ids))
        )
        for p in persons_result.scalars():
            person_map[p.person_id] = p

    # Build vehicle lookup for plate
    vehicle_ids = [d.vehicle_id for d in dispatches if d.vehicle_id]
    vehicle_map = {}
    if vehicle_ids:
        from app.models.person import Vehicle as VehicleModel
        vehicles_result = await db.execute(
            select(VehicleModel).where(VehicleModel.vehicle_id.in_(vehicle_ids))
        )
        for v in vehicles_result.scalars():
            vehicle_map[v.vehicle_id] = v

    return [
        {
            "order_id": d.order_id,
            "dispenser_id": d.dispenser_id,
            "hose_id": d.hose_id or 1,
            "side": hose_map[d.hose_id].side if d.hose_id and d.hose_id in hose_map else "A",
            "grade": d.grade_id or "DIESEL",
            "preset_type": "MONEY",
            "preset_value": "0",
            "unit_price": detail_map[d.dispatch_id].unit_price if d.dispatch_id in detail_map else (d.total or 0),
            "price_without_subsidy": float(detail_map[d.dispatch_id].price_without_subsidy) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].price_without_subsidy is not None else None,
            "subsidy_per_unit": float(detail_map[d.dispatch_id].subsidy_amount / detail_map[d.dispatch_id].quantity) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].quantity and detail_map[d.dispatch_id].quantity > 0 else 0.0,
            "subsidy_amount": float(detail_map[d.dispatch_id].subsidy_amount) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].subsidy_amount is not None else 0.0,
            "quantity": detail_map[d.dispatch_id].quantity if d.dispatch_id in detail_map else 0,
            "payment_method": "EFECTIVO",
            "customer_id": person_map[d.person_id].id_number if d.person_id and d.person_id in person_map else None,
            "customer_name": person_map[d.person_id].name if d.person_id and d.person_id in person_map else None,
            "customer_address": person_map[d.person_id].address if d.person_id and d.person_id in person_map else None,
            "customer_phone": person_map[d.person_id].phone if d.person_id and d.person_id in person_map else None,
            "plate": vehicle_map[d.vehicle_id].plate if d.vehicle_id and d.vehicle_id in vehicle_map else None,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "shift_id": d.shift_id,
            "authorized_by_user_id": d.authorized_by_user_id,
            "final_amount": float(d.total or 0),
            "final_volume": str(detail_map[d.dispatch_id].quantity) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].quantity else None,
            "invoice_number": d.sequential_number,
            "access_key": d.access_key,
            "credit_contract_id": d.credit_contract_id,
            "credit_status": d.credit_status,
            "sri_status": d.sri_status,
            "key49_access_key": d.key49_access_key,
        }
        for d in dispatches
    ]
