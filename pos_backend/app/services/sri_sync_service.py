"""Background reconciler for SRI/Key49 dispatches stuck in PENDING.

WHY THIS EXISTS
---------------
The electronic invoice flow is fire-and-forget: after the sale, a small
background poller checks Key49 for ~20 seconds (10 attempts × 2s). When
Key49/SRI takes longer than that (observed ~90–120s), the invoice IS
authorized but our dispatch stays ``sri_status='PENDING'`` forever — a
silent desync.

This service periodically reconciles those ``PENDING`` dispatches that
already carry a ``key49_invoice_id`` (i.e. the invoice was sent) by reading
their real status from Key49.

SAFETY / NON-INVASIVE
---------------------
* It ONLY reads Key49 and updates the local status of rows that are
  ``sri_status='PENDING'`` AND have a ``key49_invoice_id``.
* It NEVER re-emits invoices (no calls to ``emitir_factura``).
* Gated by ``system_config['sri_sync_enabled']`` (default off) and only
  started when not testing.
* Highly defensive: per-item and per-cycle try/except; a failure can never
  propagate to request handling or the sale flow.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ECUADOR_TZ
from app.database import async_session
from app.models.company import SystemConfig
from app.models.dispatch import Dispatch
from app.services.key49_service import _get_key49_config

logger = logging.getLogger("pos.sri_sync")

# ── Configuration ──────────────────────────────────────────
SYNC_INTERVAL_SECONDS = 120     # How often the reconciler runs
SYNC_MIN_AGE_SECONDS = 90       # Skip rows younger than this (live poller runs first)
SYNC_MAX_AGE_HOURS = 72         # Don't auto-reconcile very old rows
MAX_PER_CYCLE = 50              # Cap rows processed per cycle
FETCH_DELAY_SECONDS = 0.3       # Space GETs (Key49 GET limit: 200/window)

FINAL_STATUSES = ("AUTHORIZED", "NOTIFIED")


async def _is_enabled(db: AsyncSession) -> bool:
    cfg = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "sri_sync_enabled")
    )).scalar_one_or_none()
    return cfg is not None and (cfg.value or "").strip().lower() == "true"


async def sync_one(db: AsyncSession, dispatch: Dispatch, config: dict) -> str | None:
    """Read one invoice from Key49 and update the local status.

    Returns the new status (str) when updated, else None. Never raises.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"{config['base_url']}/invoices/{dispatch.key49_invoice_id}",
                headers={"Authorization": f"Bearer {config['api_key']}"},
            )
    except Exception as exc:  # noqa: BLE001 — defensive: never break the loop
        logger.warning("sri_sync: dispatch %s GET failed: %s", dispatch.dispatch_id, exc)
        return None

    if resp.status_code != 200:
        # 404 or transient error: leave the row untouched for manual review.
        return None

    try:
        data = resp.json().get("data", {})
    except Exception:  # noqa: BLE001
        return None

    new_status = data.get("status")
    if not new_status:
        return None

    dispatch.sri_status = new_status
    if data.get("access_key"):
        dispatch.key49_access_key = data["access_key"]

    if new_status in FINAL_STATUSES:
        auth_raw = data.get("authorization_date")
        if auth_raw:
            try:
                dispatch.sri_authorization_date = datetime.fromisoformat(
                    auth_raw.replace("Z", "+00:00")
                )
            except ValueError:
                dispatch.sri_authorization_date = datetime.now(ECUADOR_TZ)
        elif dispatch.sri_authorization_date is None:
            dispatch.sri_authorization_date = datetime.now(ECUADOR_TZ)

    msgs = data.get("sri_messages") or []
    dispatch.sri_messages = (
        json.dumps([m.get("message", "") for m in msgs])[:500] if msgs else None
    )

    await db.commit()
    logger.info(
        "sri_sync: dispatch %s reconciled -> %s",
        dispatch.dispatch_id, new_status,
    )
    return new_status


async def sync_pending_sent(db: AsyncSession | None = None) -> dict:
    """Reconcile PENDING dispatches that already have a Key49 reference.

    Returns {"scanned": N, "updated": M, "enabled": bool}.
    """
    own_session = db is None
    if own_session:
        db = async_session()

    try:
        if not await _is_enabled(db):
            return {"scanned": 0, "updated": 0, "enabled": False}

        now = datetime.now(ECUADOR_TZ)
        min_age = now - timedelta(seconds=SYNC_MIN_AGE_SECONDS)
        max_age = now - timedelta(hours=SYNC_MAX_AGE_HOURS)

        rows = (await db.execute(
            select(Dispatch).where(
                Dispatch.sri_status == "PENDING",
                Dispatch.key49_invoice_id.isnot(None),
                Dispatch.created_at <= min_age,
                Dispatch.created_at >= max_age,
            ).order_by(Dispatch.created_at.desc()).limit(MAX_PER_CYCLE)
        )).scalars().all()

        if not rows:
            return {"scanned": 0, "updated": 0, "enabled": True}

        config = await _get_key49_config(db)
        if not config.get("api_key"):
            return {"scanned": 0, "updated": 0, "enabled": True}

        updated = 0
        for dispatch in rows:
            result = await sync_one(db, dispatch, config)
            if result:
                updated += 1
            if FETCH_DELAY_SECONDS > 0:
                await asyncio.sleep(FETCH_DELAY_SECONDS)

        return {"scanned": len(rows), "updated": updated, "enabled": True}

    except Exception:  # noqa: BLE001 — must never propagate
        logger.exception("sri_sync: cycle error")
        return {"scanned": 0, "updated": 0, "enabled": True}
    finally:
        if own_session:
            await db.close()


async def run_sri_sync_loop() -> None:
    """Infinite background loop, started from the FastAPI lifespan."""
    logger.info(
        "sri_sync: started (interval=%ds, min_age=%ds, max_age=%dh)",
        SYNC_INTERVAL_SECONDS, SYNC_MIN_AGE_SECONDS, SYNC_MAX_AGE_HOURS,
    )
    while True:
        try:
            result = await sync_pending_sent()
            if result.get("updated"):
                logger.info(
                    "sri_sync: cycle completed — %d/%d reconciled",
                    result["updated"], result["scanned"],
                )
        except Exception:  # noqa: BLE001
            logger.exception("sri_sync: unexpected loop error")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
