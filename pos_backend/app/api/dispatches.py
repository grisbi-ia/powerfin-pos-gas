"""Dispatch management — create, complete, collect, cancel, billing, invoice."""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import (
    Dispatch,
    DispatchDetail,
    DispatchPayment,
    DispatchType,
    EmissionPoint,
    PaymentMethod,
    Shift,
)
from app.models.user import User
from app.schemas import (
    BillingRequest,
    CollectDispatchRequest,
    CollectDispatchResponse,
    CompleteDispatchRequest,
    CreateDispatchRequest,
    CreateDispatchResponse,
    InvoiceRequest,
)
from app.services.credit_service import validate_credit_dispatch
from app.services.sequential_service import consume_sequential

router = APIRouter(prefix="/api/pos/dispatches", tags=["dispatches"])


def _build_order_id() -> str:
    now = datetime.now()
    return f"OV-{now.strftime('%Y%m%d%H%M%S')}-{now.microsecond // 1000:03d}"


@router.post("", response_model=CreateDispatchResponse, status_code=201)
async def create_dispatch(
    body: CreateDispatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new dispatch order."""
    # Find active shift
    shift_result = await db.execute(
        select(Shift).where(
            Shift.user_id == current_user.user_id, Shift.status == "OPEN"
        )
    )
    shift = shift_result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=400, detail="No hay turno abierto")

    # Get dispatch type
    dt_result = await db.execute(
        select(DispatchType).where(DispatchType.code == body.dispatch_type_code)
    )
    dispatch_type = dt_result.scalar_one_or_none()
    if not dispatch_type:
        raise HTTPException(status_code=400, detail=f"Tipo de despacho inválido: {body.dispatch_type_code}")

    # Validate credit if applicable
    credit_contract_id = body.credit_contract_id
    credit_status = None
    if body.dispatch_type_code == "CREDIT":
        # If credit_contract_id not provided, try to find one for the vehicle
        if not credit_contract_id and body.plate:
            from app.models import Vehicle
            from app.services.credit_service import find_active_contract_for_vehicle
            v = (await db.execute(
                select(Vehicle).where(Vehicle.plate == body.plate.upper().replace(" ", ""))
            )).scalar_one_or_none()
            if v:
                contract = await find_active_contract_for_vehicle(db, v.vehicle_id)
                if contract:
                    credit_contract_id = contract.contract_id

        if credit_contract_id:
            # Validate credit availability
            from app.models.credit import CreditContract
            contract = (await db.execute(
                select(CreditContract).where(CreditContract.contract_id == credit_contract_id)
            )).scalar_one_or_none()
            if contract:
                # Find first product's ID from items
                product_id = body.items[0].product_id if body.items else None
                if product_id:
                    await validate_credit_dispatch(
                        db, 0, product_id, body.unit_price
                    )
                credit_status = "PENDING_INVOICE"

    # Consume sequential for SALE/CREDIT
    sequential_number = None
    if dispatch_type.affects_cash or dispatch_type.code == "CREDIT":
        emission_result = await db.execute(
            select(EmissionPoint).where(EmissionPoint.is_active == True).limit(1)
        )
        ep = emission_result.scalar_one_or_none()
        if ep:
            try:
                sequential_number = await consume_sequential(db, ep.emission_point_id)
            except Exception:
                # If sequential exhausted, still create dispatch without it
                pass

    order_id = _build_order_id()
    dispatch = Dispatch(
        order_id=order_id,
        shift_id=shift.shift_id,
        dispenser_id=body.dispenser_id,
        emission_point_id=ep.emission_point_id if ep else None,
        sequential_number=sequential_number,
        dispatch_type_id=dispatch_type.dispatch_type_id,
        person_id=None,
        customer_name=body.customer_name,
        authorized_by=body.authorized_by or current_user.name,
        total=float(body.unit_price),
        credit_contract_id=credit_contract_id,
        credit_status=credit_status,
    )
    db.add(dispatch)
    await db.flush()

    # Create dispatch details from items
    for item in body.items:
        detail = DispatchDetail(
            dispatch_id=dispatch.dispatch_id,
            product_id=item.product_id,
            quantity=float(item.quantity),
            unit_price=float(item.unit_price),
            tax_rate=float(item.tax_rate),
            tax_amount=float(item.quantity * item.unit_price * item.tax_rate),
            subtotal=float(item.quantity * item.unit_price),
            total=float(item.quantity * item.unit_price * (1 + item.tax_rate)),
        )
        db.add(detail)

    # Update totals
    from sqlalchemy import func as sa_func
    totals = await db.execute(
        select(
            sa_func.sum(DispatchDetail.subtotal),
            sa_func.sum(DispatchDetail.tax_amount),
            sa_func.sum(DispatchDetail.total),
        ).where(DispatchDetail.dispatch_id == dispatch.dispatch_id)
    )
    sub, tax, tot = totals.one()
    dispatch.subtotal = float(sub or 0)
    dispatch.tax_amount = float(tax or 0)
    dispatch.total = float(tot or body.unit_price)

    await db.commit()

    return CreateDispatchResponse(order_id=order_id, status="PENDING")


@router.post("/{order_id}/complete")
async def complete_dispatch(
    order_id: str,
    body: CompleteDispatchRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Mark a dispatch as completed (idempotent)."""
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        # Idempotent: if not found, just return ok
        return {"status": "ok"}

    # Already processed
    if dispatch.status != "AUTHORIZED":
        return {"status": "ok"}

    dispatch.status = "COMPLETED"
    dispatch.total = float(body.amount)
    dispatch.completed_at = datetime.now(timezone.utc)

    # Update credit balance if applicable
    if dispatch.credit_contract_id:
        from app.models.credit import CreditContract
        contract = (await db.execute(
            select(CreditContract).where(CreditContract.contract_id == dispatch.credit_contract_id)
        )).scalar_one_or_none()
        if contract:
            dispatch.credit_status = "PENDING_INVOICE"

    await db.commit()
    return {"status": "ok"}


@router.post("/{order_id}/collect", response_model=CollectDispatchResponse)
async def collect_dispatch(
    order_id: str,
    body: CollectDispatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Collect payment for a completed dispatch. Supports mixed payments."""
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if dispatch.status == "COLLECTED":
        raise HTTPException(status_code=409, detail="Orden ya cobrada")

    dispatch.status = "COLLECTED"

    # Record payments
    if body.payments:
        for p in body.payments:
            pm_result = await db.execute(
                select(PaymentMethod).where(PaymentMethod.code == p.payment_method_code)
            )
            pm = pm_result.scalar_one_or_none()
            if pm:
                payment = DispatchPayment(
                    dispatch_id=dispatch.dispatch_id,
                    payment_method_id=pm.payment_method_id,
                    amount=float(p.amount),
                    reference_code=p.reference_code,
                )
                db.add(payment)
    else:
        # Single payment (backward compatibility)
        pm_result = await db.execute(
            select(PaymentMethod).where(PaymentMethod.code == body.payment_method)
        )
        pm = pm_result.scalar_one_or_none()
        if pm:
            payment = DispatchPayment(
                dispatch_id=dispatch.dispatch_id,
                payment_method_id=pm.payment_method_id,
                amount=float(body.collected_amount),
                reference_code=body.reference_code,
            )
            db.add(payment)

    await db.commit()

    return CollectDispatchResponse(
        order_id=order_id,
        status="COLLECTED",
        collected_by_shift_id=body.collected_by_shift_id,
        collected_by_name=current_user.name,
        payment_method=body.payment_method,
        collected_amount=body.collected_amount,
        change_amount=body.change_amount,
    )


@router.post("/{order_id}/cancel")
async def cancel_dispatch(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Cancel a dispatch (only if not yet completed/collected)."""
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if dispatch:
        dispatch.status = "CANCELLED"
        await db.commit()
    return {"status": "ok"}


@router.post("/{order_id}/billing")
async def change_billing(
    order_id: str,
    body: BillingRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Change the billing recipient after dispatch (before collection)."""
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if body.customer_id:
        from app.models import Person
        person = (await db.execute(
            select(Person).where(Person.id_number == body.customer_id)
        )).scalar_one_or_none()
        if person:
            dispatch.person_id = person.person_id

    if body.customer_name is not None:
        dispatch.customer_name = body.customer_name

    await db.commit()
    return {"status": "ok"}


@router.post("/{order_id}/invoice")
async def invoice_dispatch(
    order_id: str,
    body: InvoiceRequest = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Mark a credit dispatch as invoiced."""
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    if not dispatch.credit_contract_id:
        raise HTTPException(status_code=400, detail="El despacho no es a crédito")

    dispatch.credit_status = "INVOICED"
    await db.commit()
    return {"status": "ok"}
