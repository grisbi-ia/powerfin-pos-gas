"""Shift management — open, current, close."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
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
        s.closed_at = datetime.now(timezone.utc)

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
    shift.closed_at = datetime.now(timezone.utc)
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

    # Cash movements
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

    expected = float(shift.opening_cash) + income + sales_cash - expense
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

    # Build person lookup for customer_name
    person_ids = [d.person_id for d in dispatches if d.person_id]
    person_map = {}
    if person_ids:
        from app.models import Person as PersonModel
        persons_result = await db.execute(
            select(PersonModel).where(PersonModel.person_id.in_(person_ids))
        )
        for p in persons_result.scalars():
            person_map[p.person_id] = p

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
            "quantity": detail_map[d.dispatch_id].quantity if d.dispatch_id in detail_map else 0,
            "payment_method": "EFECTIVO",
            "customer_id": None,
            "customer_name": person_map[d.person_id].name if d.person_id and d.person_id in person_map else None,
            "plate": None,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "shift_id": d.shift_id,
            "authorized_by_user_id": d.authorized_by_user_id,
            "final_amount": d.subtotal if d.subtotal else d.total,
            "final_volume": str(detail_map[d.dispatch_id].quantity) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].quantity else None,
            "invoice_number": None,
            "credit_contract_id": d.credit_contract_id,
            "credit_status": d.credit_status,
        }
        for d in dispatches
    ]
