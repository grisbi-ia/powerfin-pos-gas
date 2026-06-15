"""Shift management — open, current, close."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import ECUADOR_TZ
from app.database import get_db
from app.models import CashMovement, Dispatch, DispatchPayment, Shift
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

    # Count dispatches
    dispatch_count = await db.scalar(
        select(func.count()).where(
            Dispatch.shift_id == shift_id, Dispatch.status != "CANCELLED"
        )
    ) or 0

    # Sum sales paid in cash — payment_method_id=1 is always EFECTIVO
    # (shift_id is updated to collector's shift at collection time)
    sales_cash = await db.scalar(
        select(func.coalesce(func.sum(DispatchPayment.amount), 0))
        .select_from(DispatchPayment)
        .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.shift_id == shift_id,
            Dispatch.status == "COLLECTED",
            DispatchPayment.payment_method_id == 1
        )
    ) or 0.0
    sales_cash_count = await db.scalar(
        select(func.count())
        .select_from(DispatchPayment)
        .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
        .where(
            Dispatch.shift_id == shift_id,
            Dispatch.status == "COLLECTED",
            DispatchPayment.payment_method_id == 1
        )
    ) or 0

    # Cash movements — income, expense, transfers, safe drops
    income = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id,
            CashMovement.type.in_(["INCOME", "TRANSFER_IN"]),
        )
    ) or 0.0
    expense = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id,
            CashMovement.type == "EXPENSE",
        )
    ) or 0.0
    deposits = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id,
            CashMovement.type == "DEPOSIT",
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

    # Counts for each cash movement type
    income_count = await db.scalar(
        select(func.count()).where(CashMovement.shift_id == shift_id, CashMovement.type.in_(["INCOME", "TRANSFER_IN"]))
    ) or 0
    expense_count = await db.scalar(
        select(func.count()).where(CashMovement.shift_id == shift_id, CashMovement.type == "EXPENSE")
    ) or 0
    deposit_count = await db.scalar(
        select(func.count()).where(CashMovement.shift_id == shift_id, CashMovement.type == "DEPOSIT")
    ) or 0
    transfer_out_count = await db.scalar(
        select(func.count()).where(CashMovement.shift_id == shift_id, CashMovement.type == "TRANSFER_OUT")
    ) or 0
    safe_drop_count = await db.scalar(
        select(func.count()).where(CashMovement.shift_id == shift_id, CashMovement.type == "SAFE_DROP")
    ) or 0
    # Transfers received (INCOME with related_user_id)
    transfers_recv_amount = await db.scalar(
        select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "TRANSFER_IN"
        )
    ) or 0.0
    transfers_recv_count = await db.scalar(
        select(func.count()).where(
            CashMovement.shift_id == shift_id, CashMovement.type == "TRANSFER_IN"
        )
    ) or 0

    # Non-cash sales breakdown by payment method
    non_cash_sales = []
    pay_breakdown = await db.execute(
        select(
            PaymentMethod.code, PaymentMethod.name,
            func.coalesce(func.sum(DispatchPayment.amount), 0),
            func.count()
        )
        .select_from(DispatchPayment)
        .join(Dispatch, DispatchPayment.dispatch_id == Dispatch.dispatch_id)
        .join(PaymentMethod, DispatchPayment.payment_method_id == PaymentMethod.payment_method_id)
        .where(
            Dispatch.shift_id == shift_id,
            Dispatch.status == "COLLECTED",
            DispatchPayment.payment_method_id != 1
        )
        .group_by(PaymentMethod.code, PaymentMethod.name)
    )
    for row in pay_breakdown:
        non_cash_sales.append({
            "method_code": row[0],
            "method_name": row[1],
            "total": float(row[2] or 0),
            "count": int(row[3] or 0),
        })

    # Expected cash balance: opening + income + sales - expenses - deposits - transfers - safe_drops
    # Employee must zero out their cash BEFORE closing (via deposits/transfers).
    # POSITIVE expected → money NOT deposited → FALTANTE (shortage)
    # NEGATIVE expected → MORE money deposited than expected → SOBRANTE (surplus)
    expected = float(shift.opening_cash) + float(income) + float(sales_cash) - float(expense) - float(deposits) - float(transfers_out) - float(safe_drops)

    if expected > 0:
        shift.shortage = round(expected, 2)
        shift.surplus = 0
    elif expected < 0:
        shift.surplus = round(abs(expected), 2)
        shift.shortage = 0
    else:
        shift.surplus = 0
        shift.shortage = 0

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
        surplus=shift.surplus or 0,
        shortage=shift.shortage or 0,
        total_sales=dispatch_count,
        total_volume=0,
        dispatch_count=dispatch_count,
        accounting_cash_code=current_user.accounting_cash_code,
        accounting_branch_code=branch_code,
        cash_income=round(float(income), 2),
        cash_income_count=income_count,
        cash_expense=round(float(expense), 2),
        cash_expense_count=expense_count,
        cash_deposits=round(float(deposits), 2),
        cash_deposits_count=deposit_count,
        cash_transfers_out=round(float(transfers_out), 2),
        cash_transfers_out_count=transfer_out_count,
        cash_transfers_in=round(float(transfers_recv_amount), 2),
        cash_transfers_in_count=transfers_recv_count,
        cash_safe_drops=round(float(safe_drops), 2),
        cash_safe_drops_count=safe_drop_count,
        sales_cash=round(float(sales_cash), 2),
        sales_cash_count=sales_cash_count,
        non_cash_sales=non_cash_sales,
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
            "customer_email": person_map[d.person_id].email if d.person_id and d.person_id in person_map else None,
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
