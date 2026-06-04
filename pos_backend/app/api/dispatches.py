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
    Dispenser,
    EmissionPoint,
    PaymentMethod,
    Person,
    Shift,
    Vehicle,
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

    # Consume sequential for SALE/CREDIT — each dispenser has its own emission point
    sequential_number = None
    ep = None
    if dispatch_type.affects_cash or dispatch_type.code == "CREDIT":
        dispenser_result = await db.execute(
            select(Dispenser).where(Dispenser.dispenser_id == body.dispenser_id)
        )
        dispenser_obj = dispenser_result.scalar_one_or_none()
        if dispenser_obj and dispenser_obj.emission_point_id:
            ep_result = await db.execute(
                select(EmissionPoint).where(
                    EmissionPoint.emission_point_id == dispenser_obj.emission_point_id,
                    EmissionPoint.is_active == True,
                )
            )
            ep = ep_result.scalar_one_or_none()
        if ep:
            try:
                sequential_number = await consume_sequential(db, ep.emission_point_id)
            except Exception:
                # If sequential exhausted, still create dispatch without it
                pass

    order_id = _build_order_id()

    # Resolve hose → grade → product → tax for dispatch detail
    hose_id = None
    grade_id = None
    product_id = None
    tax_rate = Decimal("0")
    if body.hose_id:
        from app.models.dispenser import Hose
        from app.models.product import Grade as GradeModel, Product as ProductModel
        from app.models import TaxType
        hose_result = await db.execute(
            select(Hose).where(Hose.hose_id == body.hose_id)
        )
        hose = hose_result.scalar_one_or_none()
        if hose:
            hose_id = hose.hose_id
            grade_id = hose.grade_id
            # Resolve product and tax rate from grade
            grade_obj = (await db.execute(
                select(GradeModel).where(GradeModel.code == hose.grade_id)
            )).scalar_one_or_none()
            if grade_obj:
                product_obj = (await db.execute(
                    select(ProductModel).where(ProductModel.product_id == grade_obj.product_id)
                )).scalar_one_or_none()
                if product_obj:
                    product_id = product_obj.product_id
                    if product_obj.tax_type_id:
                        tax_obj = (await db.execute(
                            select(TaxType).where(TaxType.tax_type_id == product_obj.tax_type_id)
                        )).scalar_one_or_none()
                        if tax_obj:
                            tax_rate = tax_obj.rate

    # Resolve customer_id (id_number) → person_id
    person_id = None
    if body.customer_id:
        person_result = await db.execute(
            select(Person).where(
                Person.id_number == body.customer_id,
                Person.is_active == True,
            )
        )
        person = person_result.scalar_one_or_none()
        if person:
            person_id = person.person_id

    # Resolve plate → vehicle_id
    vehicle_id = None
    if body.plate:
        cleaned_plate = body.plate.upper().replace(" ", "").replace("-", "")
        vehicle_result = await db.execute(
            select(Vehicle).where(Vehicle.plate == cleaned_plate)
        )
        vehicle = vehicle_result.scalar_one_or_none()
        if vehicle:
            vehicle_id = vehicle.vehicle_id
            # Also link person if not already set
            if not person_id and vehicle.person_id:
                person_id = vehicle.person_id

    dispatch = Dispatch(
        order_id=order_id,
        shift_id=shift.shift_id,
        dispenser_id=body.dispenser_id,
        emission_point_id=ep.emission_point_id if ep else None,
        sequential_number=sequential_number,
        dispatch_type_id=dispatch_type.dispatch_type_id,
        person_id=person_id,
        vehicle_id=vehicle_id,
        authorized_by_user_id=current_user.user_id,
        total=0,
        subtotal=0,
        tax_amount=0,
        credit_contract_id=credit_contract_id,
        credit_status=credit_status,
        hose_id=hose_id,
        grade_id=grade_id,
    )
    db.add(dispatch)
    await db.flush()

    # Create dispatch detail line with product info (quantity=0 until completed)
    if product_id:
        unit_price_dec = Decimal(str(body.unit_price))
        detail = DispatchDetail(
            dispatch_id=dispatch.dispatch_id,
            product_id=product_id,
            quantity=0,
            unit_price=float(unit_price_dec),
            tax_rate=float(tax_rate),
            subtotal=0,
            tax_amount=0,
            total=0,
        )
        db.add(detail)
        await db.flush()

        # Update dispatch totals from detail (subtotal will be 0 until completed)
        dispatch.subtotal = 0
        dispatch.tax_amount = 0
        dispatch.total = 0

    # Fallback: if items were sent explicitly, use them
    if body.items:
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

        # Update totals from items
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
        dispatch.total = float(tot or 0)

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
    dispatch.completed_at = datetime.now(timezone.utc)

    # Update dispatch details with actual volume and recalculate totals
    amount_dec = Decimal(str(body.amount))
    volume_dec = Decimal(str(body.volume)) if body.volume and body.volume != "0" else Decimal("0")
    
    detail_result = await db.execute(
        select(DispatchDetail).where(DispatchDetail.dispatch_id == dispatch.dispatch_id)
    )
    details = detail_result.scalars().all()
    if details:
        # Use first detail's unit_price and tax_rate for calculations
        first_detail = details[0]
        unit_price_dec = Decimal(str(first_detail.unit_price))
        tax_rate_dec = Decimal(str(first_detail.tax_rate))
        
        if float(volume_dec) > 0:
            # Distribute volume across details (usually just 1)
            vol_per_detail = float(volume_dec) / len(details)
            for det in details:
                det.quantity = vol_per_detail
        
        # Recalculate from Fusion amount
        subtotal_dec = amount_dec
        tax_dec = subtotal_dec - (subtotal_dec / (1 + tax_rate_dec))
        
        # Update each detail proportionally
        for i, det in enumerate(details):
            share = Decimal("1") / len(details) if len(details) > 0 else Decimal("1")
            det.subtotal = float(subtotal_dec * share)
            det.tax_amount = float(tax_dec * share)
            det.total = float(subtotal_dec * share)
        
        # Update dispatch totals
        dispatch.subtotal = float(subtotal_dec)
        dispatch.tax_amount = float(tax_dec)
        dispatch.total = float(subtotal_dec)
    else:
        # Fallback: no detail exists yet (legacy dispatch)
        dispatch.total = float(amount_dec)
        dispatch.subtotal = float(amount_dec)
        dispatch.tax_amount = 0

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
    dispatch.shift_id = body.collected_by_shift_id  # cash belongs to collector's shift

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
        person = (await db.execute(
            select(Person).where(
                Person.id_number == body.customer_id,
                Person.is_active == True,
            )
        )).scalar_one_or_none()
        if not person:
            raise HTTPException(
                status_code=404,
                detail=f"Persona no encontrada: {body.customer_id}",
            )
        dispatch.person_id = person.person_id

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


@router.get("/active")
async def get_active_dispatches(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get all active dispatches across ALL open shifts.
    Used for multi-device sync: every dispatcher sees all pending orders
    regardless of who created them."""
    from app.models.dispenser import Hose

    # Get all active (non-collected, non-cancelled) dispatches from open shifts
    result = await db.execute(
        select(Dispatch)
        .join(Shift, Dispatch.shift_id == Shift.shift_id)
        .where(
            Shift.status == "OPEN",
            Dispatch.status.in_(["AUTHORIZED", "COMPLETED"]),
        )
        .order_by(Dispatch.created_at.desc())
    )
    dispatches = result.scalars().all()

    # Build hose lookup
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
            "grade": d.grade_id or "UNKNOWN",
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
