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
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ECUADOR_TZ
from app.models.dispatch import Dispatch

logger = logging.getLogger("pos.key49")

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


async def _get_provider_ruc(db: AsyncSession) -> str:
    """RUC of the software provider (GRISBI) — SRI requires it as
    'RUC Proveedor' in additional_info on EVERY invoice (individual + global).

    SELECT value FROM system_config WHERE key = 'powerfin_system_provider_ruc'

    Included unconditionally in the payload: if the key is missing/empty the
    field is still sent so Key49/SRI surfaces the error (no silent omission).
    """
    from app.models.company import SystemConfig
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "powerfin_system_provider_ruc")
    )
    cfg = result.scalar_one_or_none()
    return (cfg.value or "").strip() if cfg else ""


def _key49_error_message(resp: httpx.Response) -> str:
    """Build a readable message from a Key49 error response.

    Key49 returns structured errors like {"error": {"code": "PLAN_EXPIRED",
    "message": "Plan expirado"}}. Capture code + message (+ validation
    details) so operational failures are visible in sri_messages instead of
    a bare HTTP status code (which hides the real cause).
    """
    try:
        body = resp.json()
    except Exception:
        return f"Key49 HTTP {resp.status_code}: {resp.text[:300]}"

    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        return f"Key49 HTTP {resp.status_code}: {json.dumps(body)[:300]}"

    parts = []
    if err.get("code"):
        parts.append(str(err["code"]))
    if err.get("message"):
        parts.append(str(err["message"]))
    details = err.get("details")
    if isinstance(details, list):
        detail_msgs = [
            str(d.get("message") or d.get("field"))
            for d in details
            if isinstance(d, dict) and (d.get("message") or d.get("field"))
        ]
        if detail_msgs:
            parts.append("; ".join(detail_msgs))

    text = " \u2014 ".join(parts) if parts else json.dumps(body)[:300]
    # sri_messages column is String(500) — never exceed it
    return f"Key49 HTTP {resp.status_code}: {text}"[:500]


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
            "RUC Proveedor": await _get_provider_ruc(db),
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
    # Fall back to the plate typed at dispatch time (vehicle not registered)
    if dispatch.plate_raw:
        return dispatch.plate_raw
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
    # Never send individual invoices for public sector (PENDING_BULK_INVOICE)
    if dispatch.status == "CANCELLED":
        return False
    if dispatch.credit_status == "PENDING_BULK_INVOICE":
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
                dispatch.sri_status = "FAILED"
                dispatch.sri_messages = json.dumps([_key49_error_message(resp)])
                await db.commit()
                return False

            elif resp.status_code == 429:
                dispatch.sri_status = "PENDING"
                dispatch.sri_messages = json.dumps(
                    [_key49_error_message(resp) + " — se reintentará"]
                )
                await db.commit()
                return False

            elif resp.status_code == 409:
                # Duplicate: the invoice already exists at Key49. Key49 returns
                # error.existing_document — link it instead of losing the ref.
                existing = (
                    resp.json().get("error", {}).get("existing_document") or {}
                )
                if existing.get("id"):
                    dispatch.key49_invoice_id = existing["id"]
                    dispatch.key49_access_key = existing.get("access_key")
                    dispatch.sri_status = existing.get("status") or "NOTIFIED"
                    auth_raw = existing.get("authorization_date")
                    if auth_raw:
                        try:
                            dispatch.sri_authorization_date = datetime.fromisoformat(
                                auth_raw.replace("Z", "+00:00")
                            )
                        except ValueError:
                            dispatch.sri_authorization_date = datetime.now(ECUADOR_TZ)
                    dispatch.sri_messages = None
                    await db.commit()
                    return True
                dispatch.sri_status = "PENDING"
                dispatch.sri_messages = json.dumps([_key49_error_message(resp)])
                await db.commit()
                return False

            else:
                dispatch.sri_status = "PENDING"
                dispatch.sri_messages = json.dumps([_key49_error_message(resp)])
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


# ── PENDING retry ──────────────────────────────────────────

# Serializes retries inside the single uvicorn worker so the background loop
# and the HTTP endpoint never emit the same invoice twice.
_retry_lock = asyncio.Lock()

RETRY_INTERVAL_SECONDS = 300        # Background retry cadence
RETRY_MIN_AGE_SECONDS = 120         # Let the live post-collect emission run first
RETRY_BATCH_LIMIT = 50              # Max invoices per cycle
RETRY_MAX_AGE_DEFAULT_HOURS = 72.0  # Auto re-date window; older rows need manual re-emission
RETRY_ENABLED_KEY = "sri_retry_enabled"
RETRY_MAX_AGE_KEY = "sri_retry_max_age_hours"


def _access_key_emission_date(access_key: str | None) -> str | None:
    """First 8 digits of the SRI access key: DDMMAAAA of the emission date."""
    if not access_key or len(access_key) < 8:
        return None
    head = access_key[:8]
    return head if head.isdigit() else None


def access_key_is_for_today(access_key: str | None) -> bool:
    """True when the key was generated with today's date (Ecuador)."""
    return (
        _access_key_emission_date(access_key)
        == datetime.now(ECUADOR_TZ).strftime("%d%m%Y")
    )


async def _refresh_access_key_for_today(db: AsyncSession, dispatch: Dispatch) -> bool:
    """Regenerate the access key with today's date.

    Key49/SRI reject any invoice whose access key encodes a past date
    (HTTP 400 INVALID_ISSUE_DATE), so a retry that crosses midnight MUST get
    a fresh key. The sequential number is kept — the document was never
    accepted, so no number is burned twice.
    """
    from app.models.company import CompanyInfo
    from app.models.tributary import EmissionPoint
    from app.services.access_key_service import generate_access_key

    if not dispatch.sequential_number:
        return False
    ep = None
    if dispatch.emission_point_id:
        ep = (await db.execute(
            select(EmissionPoint).where(
                EmissionPoint.emission_point_id == dispatch.emission_point_id
            )
        )).scalar_one_or_none()
    company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one_or_none()
    if not ep or not company or not company.ruc or not company.sri_environment:
        return False
    parts = dispatch.sequential_number.split("-")
    try:
        seq = int(parts[-1]) if len(parts) >= 3 else int(dispatch.sequential_number)
    except (ValueError, TypeError):
        return False
    dispatch.access_key = generate_access_key(
        emission_date=datetime.now(ECUADOR_TZ).date(),
        doc_type=ep.doc_type or "FACTURA",
        ruc=company.ruc,
        sri_environment=company.sri_environment,
        establishment=ep.establishment,
        emission_point=ep.emission_point,
        sequential=seq,
        emission_type=company.emission_type or 1,
    )
    return True


async def retry_pending_invoices(db: AsyncSession) -> dict:
    """Send every PENDING invoice that has no Key49 reference yet.

    Runs from the background loop (``run_sri_retry_loop``) and from the HTTP
    endpoint. Serialized by a process-wide lock so the two never race.

    Rules (explicit gates, nothing swallowed):
      - ``key49_enabled=false``     → no-op.
      - ``sri_retry_enabled=false`` → no-op.
      - Same-day access key         → resend as-is.
      - Key from a previous day     → regenerate the key with today's date.
      - Older than ``sri_retry_max_age_hours`` (default 72; 0 = unlimited) →
        left PENDING for manual re-emission; never silently marked FAILED.

    Returns {retried, regenerated, expired, skipped, failed}.
    """
    if _retry_lock.locked():
        # Another retry is in flight (loop or HTTP) — do not double-emit.
        return {"retried": 0, "regenerated": 0, "expired": 0, "skipped": 0, "failed": 0}

    async with _retry_lock:
        return await _retry_pending_invoices_locked(db)


async def _retry_pending_invoices_locked(db: AsyncSession) -> dict:
    from app.models.company import SystemConfig

    configs = {
        c.key: (c.value or "")
        for c in (await db.execute(
            select(SystemConfig).where(
                SystemConfig.key.in_(
                    ["key49_enabled", RETRY_ENABLED_KEY, RETRY_MAX_AGE_KEY]
                )
            )
        )).scalars().all()
    }
    if configs.get("key49_enabled", "true").lower() == "false":
        return {"retried": 0, "regenerated": 0, "expired": 0, "skipped": 0, "failed": 0}
    if configs.get(RETRY_ENABLED_KEY, "true").lower() == "false":
        return {"retried": 0, "regenerated": 0, "expired": 0, "skipped": 0, "failed": 0}

    try:
        max_age_hours = float(configs.get(RETRY_MAX_AGE_KEY) or RETRY_MAX_AGE_DEFAULT_HOURS)
    except (TypeError, ValueError):
        max_age_hours = RETRY_MAX_AGE_DEFAULT_HOURS
    now = datetime.now(ECUADOR_TZ)
    cutoff = now - timedelta(hours=max_age_hours)
    min_age_cutoff = now - timedelta(seconds=RETRY_MIN_AGE_SECONDS)

    pending = (await db.execute(
        select(Dispatch).where(
            Dispatch.sri_status == "PENDING",
            # CRITICAL: only COLLECTED sales are invoiceable. A freshly created
            # dispatch is AUTHORIZED with the model default sri_status='PENDING'
            # (create_dispatch never sets it) — invoicing it before the fuel is
            # dispensed and paid would emit a bogus $0.00 invoice.
            Dispatch.status == "COLLECTED",
            # IS DISTINCT FROM (not !=): plain != drops rows where
            # credit_status IS NULL, which is every normal sale.
            Dispatch.credit_status.is_distinct_from("PENDING_BULK_INVOICE"),
            Dispatch.key49_invoice_id.is_(None),
            # Give the live post-collect emission a head start.
            Dispatch.created_at <= min_age_cutoff,
        ).order_by(Dispatch.created_at.asc()).limit(RETRY_BATCH_LIMIT)
    )).scalars().all()

    retried = regenerated = expired = skipped = failed = 0
    for d in pending:
        if max_age_hours > 0 and d.created_at and d.created_at < cutoff:
            # Too old to auto re-date — manual re-emission (docs/SOP_REENVIO_SRI_KEY49.md).
            expired += 1
            continue
        if not access_key_is_for_today(d.access_key):
            if not await _refresh_access_key_for_today(db, d):
                d.sri_messages = json.dumps([
                    "No se pudo regenerar la clave de acceso con la fecha de hoy "
                    "(revisar punto de emisión y datos de empresa). Reemisión manual."
                ])
                skipped += 1
                continue
            regenerated += 1
        if await emitir_factura(db, d.dispatch_id):
            retried += 1
        else:
            failed += 1

    if regenerated or skipped or failed:
        await db.commit()

    if expired:
        logger.warning(
            "sri_retry: %d PENDING invoice(s) older than %.0fh need manual "
            "re-emission (recover_pending_invoices.py)",
            expired, max_age_hours,
        )

    return {
        "retried": retried,
        "regenerated": regenerated,
        "expired": expired,
        "skipped": skipped,
        "failed": failed,
    }


async def run_sri_retry_loop() -> None:
    """Background loop that sends PENDING invoices with no Key49 reference.

    Kept separate from the read-only reconciler (``sri_sync_service``), which
    never re-emits. Self-gated by ``sri_retry_enabled`` / ``key49_enabled``.
    ``sri_retry_max_age_hours`` bounds automatic re-dating.
    """
    from app.database import async_session

    logger.info("sri_retry: loop started (interval=%ds)", RETRY_INTERVAL_SECONDS)
    while True:
        try:
            async with async_session() as db:
                result = await retry_pending_invoices(db)
            if result["retried"] or result["regenerated"] or result["failed"]:
                logger.info("sri_retry: %s", result)
        except Exception:  # noqa: BLE001 — must never break the loop
            logger.exception("sri_retry: unexpected loop error")
        await asyncio.sleep(RETRY_INTERVAL_SECONDS)


async def emitir_factura_global(
    db: AsyncSession,
    contract_id: int,
    dispatch_ids: list[int],
    access_key: str,
    sequential_number: str,
    ep,
    company,
) -> dict:
    """
    Build and send a SINGLE global SRI invoice consolidating multiple
    PENDING_BULK_INVOICE dispatches. Used for public sector liquidation.

    Returns dict with key49_invoice_id, sri_status, errors.
    """
    from app.models.credit import CreditContract
    from app.models.dispatch import DispatchDetail
    from app.models.person import Person
    from app.models.product import Product

    dispatches = (await db.execute(
        select(Dispatch)
        .where(Dispatch.dispatch_id.in_(dispatch_ids))
        .order_by(Dispatch.created_at)
    )).scalars().all()

    if not dispatches:
        return {"errors": ["No dispatches found"]}

    contract = (await db.execute(
        select(CreditContract).where(CreditContract.contract_id == contract_id)
    )).scalar_one_or_none()
    if not contract:
        return {"errors": ["Contract not found"]}

    person = (await db.execute(
        select(Person).where(Person.person_id == contract.person_id)
    )).scalar_one_or_none()
    if not person:
        return {"errors": ["Person not found"]}
    if not person.id_number:
        # Explicit failure: the recipient's identification was cleared (invalid
        # number) and must be re-captured before the global invoice is emitted.
        return {
            "errors": [
                f"El cliente {person.name} no tiene identificación registrada. "
                "Registre la cédula/RUC antes de facturar."
            ]
        }

    # Build items: one per dispatch
    items = []
    for d in dispatches:
        detail = (await db.execute(
            select(DispatchDetail).where(
                DispatchDetail.dispatch_id == d.dispatch_id
            )
        )).scalars().first()
        if not detail:
            continue

        product = (await db.execute(
            select(Product).where(Product.product_id == detail.product_id)
        )).scalar_one_or_none()

        items.append({
            "main_code": product.code if product else "FUEL",
            "description": (
                f"{product.name if product else 'Combustible'} — "
                f"Despacho {d.order_id} del "
                f"{d.created_at.strftime('%Y-%m-%d') if d.created_at else ''}"
            ),
            "unit_of_measure": product.unit if product and product.unit else "GAL",
            "quantity": float(detail.quantity) if detail.quantity else 1,
            "unit_price": round(float(detail.subtotal) / max(float(detail.quantity), 0.0001), 4),
            "discount": 0.0,
            "taxes": [{
                "code": "2",
                "rate_code": _sri_rate_code(float(detail.tax_rate)),
                "rate": float(detail.tax_rate * 100) if detail.tax_rate else 15.0,
            }],
        })

    if not items:
        return {"errors": ["No items to invoice"]}

    # Parse sequential
    parts = sequential_number.split("-")
    seq_number = parts[-1].zfill(9) if len(parts) >= 3 else sequential_number.zfill(9)

    total_amount = sum(float(d.total or 0) for d in dispatches)

    payload = {
        "access_key": access_key,
        "establishment": ep.establishment,
        "issue_point": ep.emission_point,
        "sequence_number": seq_number,
        "issue_date": _ecuador_today(),
        "recipient": {
            "id_type": _sri_id_type(person.id_type or "RUC"),
            "id": person.id_number,
            "name": person.name or "ENTIDAD PÚBLICA",
            "address": person.address or "",
            "email": person.email or "",
            "phone": person.phone or "",
        },
        "items": items,
        "payments": [{
            "payment_method": "20",
            "total": total_amount,
            "term": 0,
            "time_unit": "days",
        }],
        "additional_info": {
            "RUC Proveedor": await _get_provider_ruc(db),
            "contract_code": contract.contract_code,
            "contract_type": "SECTOR_PUBLICO",
            "dispatch_count": str(len(dispatches)),
            "dispatch_ids": ",".join(str(did) for did in dispatch_ids),
        },
    }

    # Send to Key49
    config = await _get_key49_config(db)
    if not config["api_key"]:
        return {"errors": ["Key49 API key not configured"]}

    idempotency_key = f"bulk-{contract_id}-{datetime.now(ECUADOR_TZ).timestamp()}"

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
                return {
                    "key49_invoice_id": data["id"],
                    "sri_status": "CREATED",
                    "errors": [],
                }
            elif resp.status_code == 400:
                return {
                    "sri_status": "FAILED",
                    "errors": [_key49_error_message(resp)],
                }
            else:
                return {
                    "sri_status": "PENDING",
                    "errors": [_key49_error_message(resp)],
                }

    except TERMINAL_OUT_OF_SERVICE:
        return {
            "sri_status": "PENDING",
            "errors": ["Key49 no disponible — se reintentará"],
        }
