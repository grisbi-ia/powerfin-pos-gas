"""Key49 integration — SRI electronic invoicing via Key49 API.

Flow:
  1. collect_dispatch calls emitir_factura() in background (fire-and-forget)
  2. Key49 returns {id, access_key, status: CREATED}
  3. Store key49_invoice_id, key49_access_key, sri_status=CREATED
  4. Background polling loop checks GET /invoices/:id every 2s
  5. On AUTHORIZED → store authorization_date, sri_status=AUTHORIZED
  6. On REJECTED/FAILED → store sri_messages
  7. If Key49 unreachable → sri_status stays PENDING (retry scheduler picks it up)

All HTTP calls have 10s timeout. Errors are logged, never raised to user.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ECUADOR_TZ
from app.models.dispatch import Dispatch

# ── Mapping tables ──────────────────────────────────────────

ID_TYPE_MAP = {"CED": "05", "RUC": "04", "PASAPORTE": "06"}

TAX_RATE_MAP = {
    "0.00": "0", "0.0": "0",
    "0.12": "2", "12.00": "2",
    "0.15": "4", "15.00": "4",
}
# Rate to code
RATE_CODE_BY_PERCENT = {0: "0", 12: "2", 15: "4"}

# All SRI payment codes come from the payment_methods.sri_code column.
# No hardcoded mapping — new payment methods only need a DB INSERT.


TERMINAL_OUT_OF_SERVICE = (
    httpx.ConnectError, httpx.TimeoutException,
    httpx.RemoteProtocolError, httpx.ReadError
)


async def _get_key49_config(db: AsyncSession) -> dict:
    """Read Key49 configuration from system_config table."""
    from app.models.company import SystemConfig
    result = await db.execute(
        select(SystemConfig).where(
            SystemConfig.key.in_(["key49_api_key", "key49_base_url"])
        )
    )
    configs = {c.key: c.value for c in result.scalars().all()}
    return {
        "api_key": configs.get("key49_api_key", ""),
        "base_url": configs.get("key49_base_url", "https://key49.apx5.com/v1"),
    }


def _sri_id_type(person_id_type: str) -> str:
    return ID_TYPE_MAP.get(person_id_type.upper(), "05")


def _sri_rate_code(tax_rate: float) -> str:
    pct = int(round(tax_rate * 100))
    return RATE_CODE_BY_PERCENT.get(pct, "2")


def _ecuador_today() -> str:
    return datetime.now(ECUADOR_TZ).strftime("%Y-%m-%d")


# ── Build invoice payload ──────────────────────────────────

async def _build_invoice_payload(
    db: AsyncSession, dispatch: Dispatch
) -> dict | None:
    """Build Key49 invoice JSON from dispatch + related data."""
    from app.models.dispatch import DispatchDetail, DispatchPayment
    from app.models.payment import PaymentMethod
    from app.models.person import Person
    from app.models.product import Product
    from app.models.tributary import EmissionPoint

    # Emission point
    ep = None
    if dispatch.emission_point_id:
        ep = (await db.execute(
            select(EmissionPoint).where(
                EmissionPoint.emission_point_id == dispatch.emission_point_id
            )
        )).scalar_one_or_none()

    if not ep:
        return None  # Cannot emit without emission point

    # Person (recipient)
    person = None
    if dispatch.person_id:
        person = (await db.execute(
            select(Person).where(Person.person_id == dispatch.person_id)
        )).scalar_one_or_none()

    if not person or not person.id_number:
        return None  # Cannot emit without identified recipient

    # Dispatch details (items)
    detail_result = await db.execute(
        select(DispatchDetail).where(
            DispatchDetail.dispatch_id == dispatch.dispatch_id
        )
    )
    details = detail_result.scalars().all()
    if not details:
        return None

    # Products for description
    prod_ids = [d.product_id for d in details]
    prod_result = await db.execute(
        select(Product).where(Product.product_id.in_(prod_ids))
    )
    prod_map = {p.product_id: p for p in prod_result.scalars().all()}

    # Payments
    pay_result = await db.execute(
        select(DispatchPayment).where(
            DispatchPayment.dispatch_id == dispatch.dispatch_id
        )
    )
    payments = pay_result.scalars().all()

    # Build items
    items = []
    for det in details:
        prod = prod_map.get(det.product_id)
        tax_rate_pct = float(det.tax_rate * 100) if det.tax_rate else 15.0
        items.append({
            "main_code": prod.code if prod else "FUEL",
            "description": prod.name if prod else "Combustible",
            "unit_of_measure": prod.unit if prod and prod.unit else "GAL",
            "quantity": float(det.quantity) if det.quantity else 1,
            "unit_price": round(float(det.subtotal) / max(float(det.quantity), 0.0001), 4),
            "discount": 0.0,
            "taxes": [{
                "code": "2",
                "rate_code": _sri_rate_code(float(det.tax_rate)),
                "rate": tax_rate_pct,
            }],
        })

    # Build payment info
    pay_list = []
    if payments:
        for p in payments:
            pm = (await db.execute(
                select(PaymentMethod.sri_code).where(
                    PaymentMethod.payment_method_id == p.payment_method_id
                )
            )).scalar_one_or_none()
            sri_code = pm if pm else "20"
            pay_list.append({
                "payment_method": sri_code,
                "total": float(p.amount),
                "term": 0,
                "time_unit": "days",
            })
    else:
        pay_list.append({
            "payment_method": "01",
            "total": float(dispatch.total),
            "term": 0,
            "time_unit": "days",
        })

    # Parse sequential: "001-004-000000020" → "000000020"
    seq_number = "000000001"
    if dispatch.sequential_number:
        parts = dispatch.sequential_number.split("-")
        if len(parts) >= 3:
            seq_number = parts[-1].zfill(9)
        else:
            seq_number = dispatch.sequential_number.zfill(9)

    payload = {
        "access_key": dispatch.access_key,
        "establishment": ep.establishment,
        "issue_point": ep.emission_point,
        "sequence_number": seq_number,
        "issue_date": _ecuador_today(),
        "recipient": {
            "id_type": _sri_id_type(person.id_type or "CED"),
            "id": person.id_number,
            "name": person.name or "CLIENTE",
            "address": person.address or "",
            "email": person.email or "",
            "phone": person.phone or "",
        },
        "items": items,
        "payments": pay_list,
        "additional_info": {
            "order_id": dispatch.order_id,
            "placa": await _get_plate(db, dispatch),
        },
    }
    return payload


async def _get_plate(db: AsyncSession, dispatch: Dispatch) -> str:
    if dispatch.vehicle_id:
        from app.models.person import Vehicle
        v = (await db.execute(
            select(Vehicle).where(Vehicle.vehicle_id == dispatch.vehicle_id)
        )).scalar_one_or_none()
        if v and v.plate:
            return v.plate
    return "SIN PLACA"


# ── Key49 API calls ───────────────────────────────────────

async def emitir_factura(
    db: AsyncSession,
    dispatch_id: int,
) -> bool:
    """Send invoice to Key49. Called as fire-and-forget after collect.
    Returns True if Key49 accepted, False if unreachable (will retry).
    """
    # Load dispatch fresh
    dispatch = (await db.execute(
        select(Dispatch).where(Dispatch.dispatch_id == dispatch_id)
    )).scalar_one_or_none()
    if not dispatch:
        return False

    # Don't re-send if already in processing, or if dispatch was cancelled
    if dispatch.status == "CANCELLED":
        return False
    if dispatch.sri_status and dispatch.sri_status not in ("PENDING",):
        return True

    # Build payload
    payload = await _build_invoice_payload(db, dispatch)
    if not payload:
        # Mark as FAILED — cannot build invoice (missing data)
        dispatch.sri_status = "FAILED"
        dispatch.sri_messages = json.dumps(["Datos insuficientes para factura electrónica"])
        await db.commit()
        return False

    # Get Key49 config
    config = await _get_key49_config(db)
    if not config["api_key"]:
        dispatch.sri_status = "PENDING"
        dispatch.sri_messages = json.dumps(["Key49 API key no configurada"])
        await db.commit()
        return False

    idempotency_key = f"dispatch-{dispatch_id}-{datetime.now(ECUADOR_TZ).timestamp()}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{config['base_url']}/invoices",
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": idempotency_key,
                },
                json=payload,
            )

            if resp.status_code == 202:
                data = resp.json()["data"]
                dispatch.key49_invoice_id = data["id"]
                dispatch.key49_access_key = data.get("access_key")
                dispatch.sri_status = "CREATED"
                dispatch.sri_messages = None
                await db.commit()
                # Start background polling
                asyncio.create_task(_poll_autorizacion(
                    dispatch_id, data["id"], config
                ))
                return True

            elif resp.status_code == 400:
                err = resp.json()
                dispatch.sri_status = "FAILED"
                dispatch.sri_messages = json.dumps(
                    [d.get("message", "") for d in err.get("error", {}).get("details", [])]
                ) or err.get("error", {}).get("message", "Validation error")
                await db.commit()
                return False

            elif resp.status_code == 429:
                dispatch.sri_status = "PENDING"
                dispatch.sri_messages = json.dumps(["Rate limit — se reintentará"])
                await db.commit()
                return False

            else:
                dispatch.sri_status = "PENDING"
                dispatch.sri_messages = json.dumps([f"Key49 HTTP {resp.status_code}"])
                await db.commit()
                return False

    except TERMINAL_OUT_OF_SERVICE:
        # Unreachable — stays PENDING for retry
        dispatch.sri_status = "PENDING"
        dispatch.sri_messages = json.dumps(["Key49 no disponible — se reintentará"])
        await db.commit()
        return False


async def _poll_autorizacion(
    dispatch_id: int,
    key49_invoice_id: str,
    config: dict,
    max_intentos: int = 10,
):
    """Background task: poll Key49 until AUTHORIZED/REJECTED/FAILED."""
    from app.database import async_session

    for i in range(max_intentos):
        await asyncio.sleep(2)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{config['base_url']}/invoices/{key49_invoice_id}",
                    headers={"Authorization": f"Bearer {config['api_key']}"},
                )

                if resp.status_code != 200:
                    continue

                data = resp.json()["data"]
                status = data["status"]

                # Use own DB session for updates
                async with async_session() as session:
                    await session.execute(
                        update(Dispatch)
                        .where(Dispatch.dispatch_id == dispatch_id)
                        .values(
                            sri_status=status,
                            key49_access_key=data.get("access_key"),
                            sri_authorization_date=(
                                datetime.now(ECUADOR_TZ)
                                if status in ("AUTHORIZED", "NOTIFIED") else None
                            ),
                            sri_messages=(
                                json.dumps([
                                    m.get("message", "")
                                    for m in data.get("sri_messages", [])
                                ]) if data.get("sri_messages") else None
                            ),
                        )
                    )
                    await session.commit()

                if status in ("AUTHORIZED", "REJECTED", "FAILED", "NOTIFIED"):
                    return

        except TERMINAL_OUT_OF_SERVICE:
            continue

    # Max retries exhausted
    async with async_session() as session:
        await session.execute(
            update(Dispatch)
            .where(Dispatch.dispatch_id == dispatch_id)
            .values(
                sri_status="PENDING",
                sri_messages=json.dumps(["Polling timeout — se reintentará"]),
            )
        )
        await session.commit()


async def consultar_estado(
    db: AsyncSession,
    dispatch_id: int,
) -> dict:
    """Get current SRI status for a dispatch."""
    dispatch = (await db.execute(
        select(Dispatch).where(Dispatch.dispatch_id == dispatch_id)
    )).scalar_one_or_none()

    if not dispatch:
        return {"error": "Dispatch not found"}

    return {
        "dispatch_id": dispatch_id,
        "order_id": dispatch.order_id,
        "sri_status": dispatch.sri_status,
        "key49_access_key": dispatch.key49_access_key,
        "sri_authorization_date": (
            dispatch.sri_authorization_date.isoformat()
            if dispatch.sri_authorization_date else None
        ),
        "sri_messages": (
            json.loads(dispatch.sri_messages)
            if dispatch.sri_messages else None
        ),
    }


async def retry_pending_invoices(db: AsyncSession) -> dict:
    """Retry all dispatches with sri_status = PENDING.
    Called periodically by the scheduler.
    
    Respects key49_enabled flag. Skips invoices older than 24h.
    Returns {retried: N, expired: N}.
    """
    # Check if Key49 is enabled
    from app.models.company import SystemConfig
    cfg_result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "key49_enabled")
    )
    cfg = cfg_result.scalar_one_or_none()
    if cfg and cfg.value.lower() == "false":
        return {"retried": 0, "expired": 0}

    result = await db.execute(
        select(Dispatch).where(
            Dispatch.sri_status == "PENDING",
            Dispatch.status != "CANCELLED"
        )
    )
    pending = result.scalars().all()
    
    retried = 0
    expired = 0
    ecuador_now = datetime.now(ECUADOR_TZ)
    cutoff = ecuador_now - timedelta(hours=24)
    
    for d in pending:
        # Skip invoices older than 24h — SRI rejects past-date
        # d.created_at comes from DB with Ecuador offset (-05); compare directly
        if d.created_at and d.created_at < cutoff:
            d.sri_status = "FAILED"
            d.sri_messages = json.dumps(["Vencida: más de 24h desde emisión. SRI rechaza fecha pasada."])
            expired += 1
            continue
        
        success = await emitir_factura(db, d.dispatch_id)
        if success:
            retried += 1
    
    
    if expired > 0 or retried > 0:
        await db.commit()
    
    return {"retried": retried, "expired": expired}
