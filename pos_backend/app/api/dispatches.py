"""Dispatch management — create, complete, collect, cancel, billing, invoice."""

import logging
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import ECUADOR_TZ
from app.database import get_db
from app.models import (
    Dispatch,
    DispatchDetail,
    DispatchPayment,
    DispatchType,
    Dispenser,
    EmissionPoint,
    Hose,
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
    CompleteByPumpRequest,
    CompleteDispatchRequest,
    CreateDispatchRequest,
    CreateDispatchResponse,
    InvoiceRequest,
)
from app.services.credit_service import validate_credit_dispatch
from app.services.sequential_service import consume_sequential
from app.services.access_key_service import generate_access_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pos/dispatches", tags=["dispatches"])


async def _key49_background(dispatch_id: int):
    """Fire-and-forget Key49 invoice emission with its own DB session."""
    from app.database import async_session
    from app.services.key49_service import emitir_factura
    async with async_session() as session:
        # Check if Key49 is enabled
        from app.models.company import SystemConfig
        result = await session.execute(
            select(SystemConfig).where(SystemConfig.key == "key49_enabled")
        )
        cfg = result.scalar_one_or_none()
        if cfg and cfg.value.lower() == "false":
            return  # Key49 disabled — invoice stays PENDING, no attempt
        try:
            await emitir_factura(session, dispatch_id)
        except Exception:
            pass


def _build_order_id() -> str:
    now = datetime.now(ECUADOR_TZ)
    return f"OV-{now.strftime('%Y%m%d%H%M%S')}-{now.microsecond // 1000:03d}"


@router.post("", response_model=CreateDispatchResponse, status_code=201)
async def create_dispatch(
    body: CreateDispatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new dispatch order."""
    # ═══ Guard: prevent double-authorization on the same hose ═══
    # Two dispatchers may open the sale wizard for the same dispenser.
    # If A authorizes first, B must be blocked from authorizing again.
    # pg_advisory_xact_lock prevents the theoretical race condition
    # (both checking simultaneously) — released automatically on commit/rollback.
    # Uses raw SQL to bypass SQLAlchemy statement cache (which can return
    # stale results and allow double-authorization).
    from sqlalchemy import text
    await db.execute(text("SELECT pg_advisory_xact_lock(:hose_id)"), {"hose_id": body.hose_id})

    active_result = await db.execute(
        text("SELECT 1 FROM dispatches WHERE hose_id = :hid AND status = ANY(ARRAY['AUTHORIZED','COMPLETED']) LIMIT 1"),
        {"hid": body.hose_id}
    )
    if active_result.scalar():
        raise HTTPException(
            status_code=409,
            detail="Este dispensador ya tiene un despacho en curso. "
                   "Cobre o cancele el despacho existente antes de autorizar uno nuevo."
        )

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
    if dispatch_type.dispatch_type_id == 2:
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
    if dispatch_type.affects_cash or dispatch_type.dispatch_type_id == 2:
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
        elif person_id:
            # Auto-create vehicle if person is known but vehicle doesn't exist yet
            new_vehicle = Vehicle(
                plate=cleaned_plate,
                person_id=person_id,
                is_active=True,
            )
            db.add(new_vehicle)
            await db.flush()
            vehicle_id = new_vehicle.vehicle_id

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
        preset_value=body.preset_value,
        preset_type=body.preset_type,
    )
    db.add(dispatch)
    await db.flush()

    # Generate SRI access key (49 digits) for electronic invoicing
    if ep and sequential_number:
        try:
            # Parse sequential number: "001-004-000000017" → 17
            parts = sequential_number.split("-")
            seq_int = int(parts[-1]) if len(parts) >= 3 else int(sequential_number)

            # Get company info for RUC and environment
            from app.models.company import CompanyInfo
            company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one_or_none()
            if company and company.ruc and company.sri_environment:
                local_date = datetime.now(ECUADOR_TZ).date()
                access_key = generate_access_key(
                    emission_date=local_date,
                    doc_type=ep.doc_type or "FACTURA",
                    ruc=company.ruc,
                    sri_environment=company.sri_environment,
                    establishment=ep.establishment,
                    emission_point=ep.emission_point,
                    sequential=seq_int,
                    emission_type=company.emission_type or 1,
                )
                dispatch.access_key = access_key
                await db.flush()
        except Exception:
            # Non-critical: access key can be regenerated later if needed
            pass

    # Create dispatch detail line with product info (quantity=0 until completed)
    if product_id:
        unit_price_dec = Decimal(str(body.unit_price))

        # Resolve base price from product for ticket printing
        base_price_dec = unit_price_dec
        if product_id:
            prod_result = await db.execute(
                select(ProductModel).where(ProductModel.product_id == product_id)
            )
            product_obj = prod_result.scalar_one_or_none()
            if product_obj and product_obj.base_price:
                base_price_dec = Decimal(str(product_obj.base_price))

        detail = DispatchDetail(
            dispatch_id=dispatch.dispatch_id,
            product_id=product_id,
            quantity=0,
            unit_price=float(unit_price_dec),
            price_without_subsidy=float(base_price_dec),
            subsidy_amount=0,
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
):
    """Mark a dispatch as completed (idempotent).
    Called by FusionBridge (no auth — internal service) and POS (double-safe).
    """
    logger.debug(f"complete_dispatch: order={order_id} amount={body.amount} volume={body.volume}")
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        # Idempotent: if not found, just return ok
        return {"status": "ok"}

    # Already processed — but allow correction if totals are 0
    # (race condition: FusionBridge wins with Wayne AM=0, POS retries with real amount)
    if dispatch.status != "AUTHORIZED":
        if dispatch.status == "COMPLETED" and float(dispatch.total or 0) == 0 and body.amount and float(body.amount) > 0:
            pass  # Proceed to correct the zero totals
        else:
            return {"status": "ok"}

    # Only update status if not already COMPLETED
    if dispatch.status == "AUTHORIZED":
        dispatch.status = "COMPLETED"
        dispatch.completed_at = datetime.now(ECUADOR_TZ)

    # Update dispatch details with actual volume and recalculate totals
    try:
        amount_dec = Decimal(str(body.amount)) if body.amount else Decimal("0")
    except Exception:
        logger.warning(f"complete_dispatch: invalid amount '{body.amount}' for {order_id}")
        amount_dec = Decimal("0")
    try:
        volume_dec = Decimal(str(body.volume)) if body.volume and body.volume != "0" else Decimal("0")
    except Exception:
        volume_dec = Decimal("0")
    
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
        
        # Wayne returns total (includes IVA). Recalculate subtotal and tax.
        # base_price in products already includes IVA — no subsidy active.
        total_dec = amount_dec
        subtotal_dec = total_dec / (1 + tax_rate_dec)
        tax_dec = total_dec - subtotal_dec

        # Update each detail proportionally
        for i, det in enumerate(details):
            share = Decimal("1") / len(details) if len(details) > 0 else Decimal("1")
            det.subtotal = float(subtotal_dec * share)
            det.tax_amount = float(tax_dec * share)
            det.total = float(total_dec * share)
            det.subsidy_amount = 0
        
        # Update dispatch totals
        dispatch.subtotal = float(subtotal_dec)
        dispatch.tax_amount = float(tax_dec)
        dispatch.total = float(total_dec)
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


@router.post("/complete-by-pump")
async def complete_dispatch_by_pump(
    body: CompleteByPumpRequest,
    db: AsyncSession = Depends(get_db),
):
    """Complete the AUTHORIZED dispatch for a given pump+hose.

    Fallback when PAY_IN (and thus orderId) is not echoed by the Wayne
    in EVT_PUMP_NEW_TRANSACTION for PRESET flows. FusionBridge calls this
    with the pump and hose numbers from the NEW_TRANSACTION event.

    No auth — internal service call from FusionBridge.
    """
    from app.models.dispenser import Hose

    # Map fusion_pump_id + fusion_hose_id to hose_id
    hose_result = await db.execute(
        select(Hose).where(
            Hose.fusion_pump_id == body.fusion_pump_id,
            Hose.fusion_hose_id == body.fusion_hose_id
        )
    )
    hose = hose_result.scalar_one_or_none()
    if not hose:
        return {"status": "ok", "detail": "no hose found"}

    # Find the AUTHORIZED dispatch for this hose (most recent first).
    # Also include COMPLETED dispatches with total=0 (Wayne race condition fix).
    # Uses raw SQL to bypass statement cache.
    dispatch_result = await db.execute(
        text("SELECT dispatch_id FROM dispatches WHERE hose_id = :hid AND status = ANY(ARRAY['AUTHORIZED','COMPLETED']) ORDER BY created_at DESC LIMIT 1"),
        {"hid": hose.hose_id}
    )
    row = dispatch_result.fetchone()
    if not row:
        return {"status": "ok", "detail": "no authorized dispatch"}

    dispatch_result = await db.execute(
        select(Dispatch).where(Dispatch.dispatch_id == row[0])
    )
    dispatch = dispatch_result.scalar_one_or_none()

    # Only update status if not already COMPLETED (allow correction of zero totals)
    if dispatch.status == "AUTHORIZED":
        dispatch.status = "COMPLETED"
        dispatch.completed_at = datetime.now(ECUADOR_TZ)
    elif dispatch.status == "COMPLETED" and float(dispatch.total or 0) > 0:
        # Already completed with real totals — nothing to do
        return {"status": "ok", "detail": "already completed with totals"}

    # Update amounts from the Wayne's NEW_TRANSACTION data
    if body.amount and float(body.amount) > 0:
        amount_dec = Decimal(str(body.amount))
        volume_dec = Decimal(str(body.volume)) if body.volume and body.volume != "0" else Decimal("0")

        detail_result = await db.execute(
            select(DispatchDetail).where(DispatchDetail.dispatch_id == dispatch.dispatch_id)
        )
        details = detail_result.scalars().all()
        if details:
            first_detail = details[0]
            unit_price_dec = Decimal(str(body.unit_price)) if body.unit_price and float(body.unit_price) > 0 else Decimal(str(first_detail.unit_price))
            tax_rate_dec = Decimal(str(first_detail.tax_rate))

            if float(volume_dec) > 0:
                vol_per_detail = float(volume_dec) / len(details)
                for det in details:
                    det.quantity = vol_per_detail

            total_dec = amount_dec
            subtotal_dec = total_dec / (1 + tax_rate_dec)
            tax_dec = total_dec - subtotal_dec

            for i, det in enumerate(details):
                share = Decimal("1") / len(details) if len(details) > 0 else Decimal("1")
                det.subtotal = float(subtotal_dec * share)
                det.tax_amount = float(tax_dec * share)
                det.total = float(total_dec * share)
                det.subsidy_amount = 0

            dispatch.subtotal = float(subtotal_dec)
            dispatch.tax_amount = float(tax_dec)
            dispatch.total = float(total_dec)
        else:
            dispatch.total = float(amount_dec)
            dispatch.subtotal = float(amount_dec)
            dispatch.tax_amount = 0
    else:
        # Keep existing totals (from preset) — better than zero
        pass

    if dispatch.credit_contract_id:
        from app.models.credit import CreditContract
        contract = (await db.execute(
            select(CreditContract).where(CreditContract.contract_id == dispatch.credit_contract_id)
        )).scalar_one_or_none()
        if contract:
            dispatch.credit_status = "PENDING_INVOICE"

    await db.commit()
    return {"status": "completed", "order_id": dispatch.order_id}


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

    if dispatch.status != "COMPLETED":
        raise HTTPException(
            status_code=409,
            detail="El despacho aún no ha terminado. "
                   "Espere a que el surtidor complete el despacho."
        )

    # Guard 1: never collect a dispatch with $0.00 total
    # (Wayne race condition, complete_dispatch never ran, or stale data)
    dispatch_total = float(dispatch.total or 0)
    if dispatch_total <= 0:
        raise HTTPException(
            status_code=409,
            detail="El despacho aún no tiene monto registrado. "
                   "Espere a que el surtidor termine de despachar."
        )

    # Guard 2: don't allow collecting at $0.00 when the dispatch has a real amount
    effective_amount = float(body.collected_amount)
    if body.payments:
        effective_amount = sum(float(p.amount) for p in body.payments)
    if effective_amount <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"El monto a cobrar es \${dispatch_total:.2f}. "
                   "No se puede cobrar \$0.00. Regrese al inicio y reintente."
        )

    dispatch.status = "COLLECTED"
    dispatch.shift_id = body.collected_by_shift_id  # cash belongs to collector's shift

    # Record payments
    if body.payments:
        for p in body.payments:
            payment = DispatchPayment(
                dispatch_id=dispatch.dispatch_id,
                payment_method_id=p.payment_method_id,
                amount=float(p.amount),
                reference_code=p.reference_code,
            )
            db.add(payment)
    else:
        # Single payment (backward compatibility)
        payment = DispatchPayment(
            dispatch_id=dispatch.dispatch_id,
            payment_method_id=body.payment_method_id,
            amount=float(body.collected_amount),
            reference_code=body.reference_code,
        )
        db.add(payment)

    # Resolve payment method name for receipt
    pm_result = await db.execute(
        select(PaymentMethod).where(PaymentMethod.payment_method_id == body.payment_method_id)
    )
    pm = pm_result.scalar_one_or_none()
    pay_method_name = pm.name if pm else ""

    await db.commit()

    # Build receipt data from persisted DB records (same as reprint uses)
    receipt_data = await _build_receipt_data(db, dispatch, pay_method_name)

    # Fire-and-forget: send invoice to SRI via Key49 (non-blocking)
    # Pass only dispatch_id — background task creates its own DB session
    try:
        import asyncio
        dispatch_id = dispatch.dispatch_id
        asyncio.create_task(_key49_background(dispatch_id))
    except Exception:
        pass  # Key49 failure never blocks the sale

    return CollectDispatchResponse(
        order_id=order_id,
        status="COLLECTED",
        collected_by_shift_id=body.collected_by_shift_id,
        collected_by_name=current_user.name,
        payment_method_id=body.payment_method_id,
        collected_amount=body.collected_amount,
        change_amount=body.change_amount,
        receipt_data=receipt_data,
    )


async def _build_receipt_data(db: AsyncSession, dispatch: Dispatch, pay_method_name: str = "") -> dict:
    """Build full receipt data from persisted DB records.
    Same data source as history reprint — ensures print and reprint are identical."""
    from app.models.company import CompanyInfo

    # Dispatch detail (volume, unit_price, subsidy)
    detail_result = await db.execute(
        select(DispatchDetail).where(DispatchDetail.dispatch_id == dispatch.dispatch_id)
    )
    detail = detail_result.scalars().first()

    # Payment — prefer caller-supplied name, fall back to DB query
    if not pay_method_name:
        pay_result = await db.execute(
            select(DispatchPayment).where(DispatchPayment.dispatch_id == dispatch.dispatch_id)
        )
        pay = pay_result.scalars().first()
        if pay:
            pm_result = await db.execute(
                select(PaymentMethod).where(PaymentMethod.payment_method_id == pay.payment_method_id)
            )
            pm = pm_result.scalar_one_or_none()
            if pm:
                pay_method_name = pm.name or pm.code or ""
        if not pay_method_name:
            pay_method_name = ""

    # Person (customer)
    person = None
    if dispatch.person_id:
        person_result = await db.execute(
            select(Person).where(Person.person_id == dispatch.person_id)
        )
        person = person_result.scalar_one_or_none()

    # Vehicle (plate)
    plate = ""
    if dispatch.vehicle_id:
        v_result = await db.execute(
            select(Vehicle).where(Vehicle.vehicle_id == dispatch.vehicle_id)
        )
        v = v_result.scalar_one_or_none()
        if v:
            plate = v.plate or ""

    # Company info
    company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one_or_none()

    # Emission point
    ep = None
    if dispatch.emission_point_id:
        ep_result = await db.execute(
            select(EmissionPoint).where(
                EmissionPoint.emission_point_id == dispatch.emission_point_id
            )
        )
        ep = ep_result.scalar_one_or_none()

    # Dispenser (for printer_ip)
    dispenser = None
    if dispatch.dispenser_id:
        d_result = await db.execute(
            select(Dispenser).where(Dispenser.dispenser_id == dispatch.dispenser_id)
        )
        dispenser = d_result.scalar_one_or_none()

    # Collector info (shift owner = the cashier who collected)
    cashier_name = ""
    if dispatch.shift_id:
        shift_result = await db.execute(
            select(User.name).join(Shift, Shift.user_id == User.user_id)
            .where(Shift.shift_id == dispatch.shift_id)
        )
        cashier_name = shift_result.scalar_one_or_none() or ""

    # Computed financials (IVA 15%)
    total = float(dispatch.total or 0)
    subtotal = round(total / 1.15, 2)
    tax = round(total - subtotal, 2)

    return {
        "printerIp": dispenser.printer_ip if dispenser and dispenser.printer_ip else "",
        "printerPort": dispenser.printer_port if dispenser else 9100,
        "dispenserId": dispatch.dispenser_id or 0,
        "fuelData": {
            "dispenserId": dispatch.dispenser_id or 0,
            "hoseId": dispatch.hose_id or 0,
            "orderId": dispatch.order_id or "",
            "volume": str(float(detail.quantity)) if detail and detail.quantity else "0",
            "amount": f"{total:.2f}",
            "unitPrice": f"{float(detail.unit_price):.7f}" if detail and detail.unit_price else "0",
            "priceWithoutSubsidy": f"{float(detail.price_without_subsidy):.4f}" if detail and detail.price_without_subsidy is not None else "",
            "subsidyPerUnit": f"{float(detail.subsidy_amount / detail.quantity):.4f}" if detail and detail.subsidy_amount and detail.quantity and detail.quantity > 0 else "",
            "subsidyAmount": f"{float(detail.subsidy_amount):.2f}" if detail and detail.subsidy_amount is not None else "",
            "paymentMethod": pay_method_name,
            "grade": dispatch.grade_id or "",
            "customerName": person.name if person else "",
            "customerId": person.id_number if person else "",
            "customerAddress": person.address if person and person.address else "",
            "customerPhone": person.phone if person and person.phone else "",
            "customerEmail": person.email if person and person.email else "",
            "plate": plate,
            "invoiceId": dispatch.sequential_number or "",
            "invoiceAuth": dispatch.access_key or "",
            "subtotal": f"{subtotal:.2f}",
            "taxLabel": "IVA 15%",
            "taxAmount": f"{tax:.2f}",
            "unit": "GAL",
            "locationName": company.commercial_name or company.name or "",
            "locationAddress": company.address or "",
            "locationRuc": company.ruc or "",
            "locationPhone": company.phone or "",
            "locationCity": company.city or "",
            "locationProvince": company.province or "",
            "locationCountry": company.country or "",
            "fiscalRegime": company.fiscal_regime or "",
            "sriEnvironment": company.sri_environment or 0,
            "emissionType": company.emission_type or 0,
            "shiftId": str(dispatch.shift_id) if dispatch.shift_id else "",
            "cashierName": cashier_name,
        },
    }


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
        dispatch.sri_status = None  # CANCELLED dispatches must never reach SRI
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

    # Build shift → cashier name lookup (collector = shift owner)
    shift_ids = list(set(d.shift_id for d in dispatches if d.shift_id))
    cashier_map = {}
    if shift_ids:
        shifts_result = await db.execute(
            select(Shift.shift_id, User.name)
            .join(User, Shift.user_id == User.user_id)
            .where(Shift.shift_id.in_(shift_ids))
        )
        for sid, uname in shifts_result:
            cashier_map[sid] = uname or ""

    # Build payment method name lookup
    pay_method_map = {}
    if dispatch_ids:
        pay_result = await db.execute(
            select(DispatchPayment.dispatch_id, PaymentMethod.name)
            .join(PaymentMethod, DispatchPayment.payment_method_id == PaymentMethod.payment_method_id)
            .where(DispatchPayment.dispatch_id.in_(dispatch_ids))
        )
        for did, pname in pay_result:
            pay_method_map[did] = pname

    return [
        {
            "order_id": d.order_id,
            "dispenser_id": d.dispenser_id,
            "hose_id": d.hose_id or 1,
            "side": hose_map[d.hose_id].side if d.hose_id and d.hose_id in hose_map else "A",
            "grade": d.grade_id or "UNKNOWN",
            "preset_type": d.preset_type or "MONEY",
            "preset_value": d.preset_value or "0",
            "unit_price": detail_map[d.dispatch_id].unit_price if d.dispatch_id in detail_map else (d.total or 0),
            "price_without_subsidy": float(detail_map[d.dispatch_id].price_without_subsidy) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].price_without_subsidy is not None else None,
            "subsidy_per_unit": float(detail_map[d.dispatch_id].subsidy_amount / detail_map[d.dispatch_id].quantity) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].quantity and detail_map[d.dispatch_id].quantity > 0 else 0.0,
            "subsidy_amount": float(detail_map[d.dispatch_id].subsidy_amount) if d.dispatch_id in detail_map and detail_map[d.dispatch_id].subsidy_amount is not None else 0.0,
            "quantity": detail_map[d.dispatch_id].quantity if d.dispatch_id in detail_map else 0,
            "payment_method": "",
            "payment_method_name": pay_method_map.get(d.dispatch_id, ""),
            "customer_id": person_map[d.person_id].id_number if d.person_id and d.person_id in person_map else None,
            "customer_name": person_map[d.person_id].name if d.person_id and d.person_id in person_map else None,
            "customer_address": person_map[d.person_id].address if d.person_id and d.person_id in person_map else None,
            "customer_phone": person_map[d.person_id].phone if d.person_id and d.person_id in person_map else None,
            "customer_email": person_map[d.person_id].email if d.person_id and d.person_id in person_map else None,
            "plate": vehicle_map[d.vehicle_id].plate if d.vehicle_id and d.vehicle_id in vehicle_map else None,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "shift_id": d.shift_id,
            "cashier_name": cashier_map.get(d.shift_id, "") if d.shift_id else "",
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


@router.get("/{order_id}/sri-status")
async def get_sri_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Get SRI electronic invoice status for a dispatch."""
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    from app.services.key49_service import consultar_estado
    return await consultar_estado(db, dispatch.dispatch_id)


@router.post("/{order_id}/retry-sri")
async def retry_single_invoice(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Manually retry SRI emission for a single dispatch (ADMIN/SUPERVISOR)."""
    if _user.role and _user.role.code not in ("ADMIN", "SUPERVISOR"):
        raise HTTPException(status_code=403, detail="Solo administradores")

    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == order_id)
    )
    dispatch = result.scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    # Reset to PENDING to allow retry (even FAILED ones)
    dispatch.sri_status = "PENDING"
    dispatch.sri_messages = None
    await db.commit()

    from app.services.key49_service import emitir_factura
    success = await emitir_factura(db, dispatch.dispatch_id)

    return {
        "order_id": order_id,
        "success": success,
        "sri_status": dispatch.sri_status,
    }


@router.post("/retry-pending-invoices")
async def retry_pending_invoices_endpoint(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Retry all pending SRI invoices. Admin/SUPERVISOR only."""
    if _user.role and _user.role.code not in ("ADMIN", "SUPERVISOR"):
        raise HTTPException(status_code=403, detail="Solo administradores")

    from app.services.key49_service import retry_pending_invoices
    result = await retry_pending_invoices(db)
    return result
