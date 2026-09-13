"""Background reconciler for SRI/Key49 dispatches stuck in a non-final state.

WHY THIS EXISTS
---------------
The electronic invoice flow is fire-and-forget: after the sale, a small
background poller checks Key49 for ~20 seconds (10 attempts × 2s). When
Key49/SRI takes longer than that (observed ~90–120s), the invoice IS
authorized but our dispatch keeps a stale status — a silent desync.

The status can get stuck in ANY non-final state, not just ``PENDING``:

* ``PENDING``  — polling timeout, the invoice exists but we never saw it.
* ``RETRY``    — Key49 was retrying; it may have succeeded later.
* ``CREATED/SIGNED/SENT/RECEIVED`` — in-flight when the poller stopped.
* ``FAILED``   — Key49 gave up, but a Key49-side reprocess can still move it
                 (observed: environment misconfig → FAILED → NOTIFIED).
* ``REJECTED`` — SRI rejected it, but Key49 can reprocess it from its UI
                 (observed: 34 docs REJECTED → NOTIFIED with no API call).

This service periodically reconciles those dispatches — any non-final status
that already carries a ``key49_invoice_id`` — by reading their real status
from Key49.

SAFETY / NON-INVASIVE
---------------------
* It ONLY reads Key49 and updates the local status of rows that are
  non-final AND have a ``key49_invoice_id``.
* It NEVER re-emits invoices (no calls to ``emitir_factura``).
* Gated by ``system_config['sri_sync_enabled']`` (default off) and only
  started when not testing.
* Highly defensive: per-item and per-cycle try/except; a failure can never
  propagate to request handling or the sale flow.
* Rows that stay stalled (``REJECTED``/``FAILED``) are re-checked at most
  once per ``STALLED_RECHECK_SECONDS`` to avoid hammering Key49 GETs.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

import httpx
from sqlalchemy import or_, select
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
# Rows in these statuses rarely change on their own (only via a manual
# Key49-side reprocess), so re-check them less often.
STALLED_STATUSES = ("REJECTED", "FAILED")
STALLED_RECHECK_SECONDS = 3600  # Re-check stalled rows at most once per hour
MAX_STALLED_TRACKED = 5000      # Cap the in-memory cooldown map

# dispatch_id -> monotonic timestamp of the last stalled re-check.
_stalled_last_check: dict[int, float] = {}


def reset_stalled_recheck_tracker() -> None:
    """Clear the in-memory stalled cooldown. Used by tests/ops."""
    _stalled_last_check.clear()


def _prune_stalled_tracker(now: float) -> None:
    if len(_stalled_last_check) <= MAX_STALLED_TRACKED:
        return
    for key in [
        k for k, ts in _stalled_last_check.items()
        if now - ts >= STALLED_RECHECK_SECONDS
    ]:
        _stalled_last_check.pop(key, None)


def _stalled_recheck_due(dispatch: Dispatch) -> bool:
    """True when a row is due to be queried.

    Non-stalled rows are always due. Stalled rows (REJECTED/FAILED) are due
    at most once per hour; the attempt is recorded here so the next cycle
    skips them. Never raises.
    """
    if dispatch.sri_status not in STALLED_STATUSES:
        return True
    now = time.monotonic()
    last = _stalled_last_check.get(dispatch.dispatch_id)
    if last is not None and (now - last) < STALLED_RECHECK_SECONDS:
        return False
    _stalled_last_check[dispatch.dispatch_id] = now
    _prune_stalled_tracker(now)
    return True


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

    access_key = data.get("access_key")
    msgs = data.get("sri_messages") or []
    new_messages = (
        json.dumps([m.get("message", "") for m in msgs])[:500] if msgs else None
    )

    # Nothing to persist? Skip the write (avoids churn on stalled rows).
    needs_auth_date = (
        new_status in FINAL_STATUSES and dispatch.sri_authorization_date is None
    )
    if (
        dispatch.sri_status == new_status
        and (not access_key or access_key == dispatch.key49_access_key)
        and new_messages == dispatch.sri_messages
        and not needs_auth_date
    ):
        return None

    dispatch.sri_status = new_status
    if access_key:
        dispatch.key49_access_key = access_key

    if new_status in FINAL_STATUSES and dispatch.sri_authorization_date is None:
        auth_raw = data.get("authorization_date")
        if auth_raw:
            try:
                dispatch.sri_authorization_date = datetime.fromisoformat(
                    str(auth_raw).replace("Z", "+00:00")
                )
            except ValueError:
                dispatch.sri_authorization_date = datetime.now(ECUADOR_TZ)
        else:
            dispatch.sri_authorization_date = datetime.now(ECUADOR_TZ)

    dispatch.sri_messages = new_messages

    await db.commit()
    logger.info(
        "sri_sync: dispatch %s reconciled -> %s",
        dispatch.dispatch_id, new_status,
    )
    return new_status


async def sync_non_final_dispatches(db: AsyncSession | None = None) -> dict:
    """Reconcile every non-final dispatch that already has a Key49 reference.

    Covers PENDING plus any other non-final state (RETRY, CREATED, SIGNED,
    SENT, RECEIVED, REJECTED, FAILED) so a Key49-side change is picked up.

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
                or_(
                    Dispatch.sri_status.is_(None),
                    Dispatch.sri_status.notin_(FINAL_STATUSES),
                ),
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
        scanned = 0
        for dispatch in rows:
            if not _stalled_recheck_due(dispatch):
                continue
            scanned += 1
            result = await sync_one(db, dispatch, config)
            if result:
                updated += 1
            if FETCH_DELAY_SECONDS > 0:
                await asyncio.sleep(FETCH_DELAY_SECONDS)

        return {"scanned": scanned, "updated": updated, "enabled": True}

    except Exception:  # noqa: BLE001 — must never propagate
        logger.exception("sri_sync: cycle error")
        return {"scanned": 0, "updated": 0, "enabled": True}
    finally:
        if own_session:
            await db.close()


async def run_sri_sync_loop() -> None:
    """Infinite background loop, started from the FastAPI lifespan."""
    logger.info(
        "sri_sync: started (interval=%ds, min_age=%ds, max_age=%dh, "
        "stalled_recheck=%ds)",
        SYNC_INTERVAL_SECONDS, SYNC_MIN_AGE_SECONDS, SYNC_MAX_AGE_HOURS,
        STALLED_RECHECK_SECONDS,
    )
    while True:
        try:
            result = await sync_non_final_dispatches()
            if result.get("updated"):
                logger.info(
                    "sri_sync: cycle completed — %d/%d reconciled",
                    result["updated"], result["scanned"],
                )
        except Exception:  # noqa: BLE001
            logger.exception("sri_sync: unexpected loop error")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
