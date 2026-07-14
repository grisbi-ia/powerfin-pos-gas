"""
Background cleanup of orphan AUTHORIZED dispatches.

When the Wayne ATO (Authorization Time Out) expires, the dispenser
cancels internally and returns to IDLE, but the POS Backend is never
notified. This leaves an AUTHORIZED + $0.00 dispatch that blocks the
hose indefinitely, requiring manual SQL intervention.

This service runs every 60 seconds and cancels dispatches that:
  - status == 'AUTHORIZED'
  - total == 0.00
  - created more than threshold seconds ago:
      * Pump IDLE → 120s (2 min — empty tank, ATO timeout, no fuel)
      * FULL preset (pump not idle) → 1800s (30 min — truck fill-ups)
      * MONEY/VOLUME preset (pump not idle) → 900s (15 min — typical ATO)
  - pump is NOT actively dispensing (verified via FusionBridge)

All cancellations are logged for audit trail.

Functions accept an optional db session for testing; when omitted they
create their own session via the app's global async_session factory.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ECUADOR_TZ
from app.database import async_session
from app.models.dispatch import Dispatch

logger = logging.getLogger("pos.cleanup")

# ── Configuration ──────────────────────────────────────────
CLEANUP_INTERVAL_SECONDS = 60   # How often to scan for orphans
ORPHAN_AGE_FULL = 1800          # FULL preset: 30 min (trucks, tankers)
ORPHAN_AGE_PRESET = 900         # MONEY/VOLUME preset: 15 min (typical ATO)
ORPHAN_AGE_IDLE = 120           # Pump IDLE + AUTHORIZED $0: 2 min (empty tank, ATO)
FUSION_BRIDGE_TIMEOUT = 5.0     # Seconds to wait for FusionBridge status
# ───────────────────────────────────────────────────────────


async def _get_fusion_pump_statuses(
    bridge_url: str
) -> dict[int, str]:
    """
    Query FusionBridge for current pump statuses.
    Returns dict: fusion_pump_id → status string (e.g. 'FUELLING', 'IDLE').
    On any error, returns empty dict (conservative: don't cancel if unsure).
    """
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(FUSION_BRIDGE_TIMEOUT)) as client:
            resp = await client.get(f"{bridge_url}/api/dispensers")
            resp.raise_for_status()
            data = resp.json()
            pumps: dict[int, str] = {}
            for fd in data.get("dispensers", []):
                pump_id = fd.get("dispenserId", 0)
                status = fd.get("status", "UNKNOWN")
                if pump_id:
                    pumps[pump_id] = status
            return pumps
    except Exception as e:
        logger.warning("dispatch_cleanup: cannot reach FusionBridge (%s) — skipping pump check", e)
        return {}


def _orphan_threshold(dispatch: Dispatch) -> int:
    """Return age threshold in seconds based on preset type.
    FULL presets (trucks, tankers) get 30 min; MONEY/VOLUME get 15 min."""
    if dispatch.preset_type == "VOLUME" and dispatch.preset_value == "FULL":
        return ORPHAN_AGE_FULL
    return ORPHAN_AGE_PRESET


async def _cancel_orphan_dispatches(db: AsyncSession | None = None) -> int:
    """
    Find and cancel AUTHORIZED $0.00 dispatches older than threshold.
    Before cancelling, verifies the pump is NOT actively dispensing
    (FUELLING / STARTING) via FusionBridge.
    Accepts an optional db session for testing.
    Returns the number of dispatches cancelled.
    """
    own_session = db is None

    if own_session:
        db = async_session()

    try:
        # ── Find all AUTHORIZED + $0.00 dispatches ───────────
        result = await db.execute(
            select(Dispatch).where(
                Dispatch.status == "AUTHORIZED",
                Dispatch.total == 0.00,
            )
        )
        candidates = result.scalars().all()

        if not candidates:
            return 0

        # ── Resolve FusionBridge URL from system_config ─────
        from app.models.company import SystemConfig
        bridge_url = "http://localhost:8090"
        cfg = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "fusion_bridge_url")
        )
        cfg_row = cfg.scalar_one_or_none()
        if cfg_row and cfg_row.value:
            bridge_url = cfg_row.value.rstrip("/")

        # ── Check FusionBridge for active pumps ──────────────
        pump_statuses = await _get_fusion_pump_statuses(bridge_url)

        # ── Build hose → fusion_pump_id mapping ──────────────
        from app.models.dispenser import Hose
        hose_ids = [d.hose_id for d in candidates if d.hose_id]
        hose_to_pump: dict[int, int] = {}
        if hose_ids:
            hoses_result = await db.execute(
                select(Hose).where(Hose.hose_id.in_(hose_ids))
            )
            for h in hoses_result.scalars():
                if h.fusion_pump_id:
                    hose_to_pump[h.hose_id] = h.fusion_pump_id

        # ── Filter: age threshold + pump not active ──────────
        now = datetime.now(ECUADOR_TZ)
        cancelled = 0
        skipped_active = 0
        skipped_age = 0

        for dispatch in candidates:
            age = int((now - dispatch.created_at).total_seconds())
            threshold = _orphan_threshold(dispatch)

            # ── Fast cancel: pump confirmed IDLE + empty tank / ATO ──
            # Only for MONEY/VOLUME presets (not FULL — those need 30 min).
            # If the pump is IDLE and the dispatch is still AUTHORIZED+$0.00,
            # no fuel was dispensed (empty tank, ATO timeout). Safe to cancel.
            pump_is_idle = False
            if dispatch.hose_id and dispatch.hose_id in hose_to_pump:
                fusion_pump = hose_to_pump[dispatch.hose_id]
                pump_status = pump_statuses.get(fusion_pump, "")
                pump_is_idle = (pump_status == "IDLE")

                if pump_status in ("FUELLING", "STARTING", "AUTHORIZED"):
                    logger.debug(
                        "dispatch_cleanup: skipping dispatch_id=%s — pump %s "
                        "is %s (still dispensing)",
                        dispatch.dispatch_id, fusion_pump, pump_status,
                    )
                    skipped_active += 1
                    continue

            if pump_is_idle and age >= ORPHAN_AGE_IDLE:
                # Fast path: pump is IDLE, no fuel was dispensed
                dispatch.status = "CANCELLED"
                dispatch.sri_status = None
                cancelled += 1
                logger.info(
                    "dispatch_cleanup: fast-cancelled dispatch_id=%s order_id=%s "
                    "hose_id=%s preset=%s/%s — pump IDLE for %ds (empty tank / ATO)",
                    dispatch.dispatch_id, dispatch.order_id, dispatch.hose_id,
                    dispatch.preset_type, dispatch.preset_value, age,
                )
                continue

            # Normal path: needs to exceed preset-specific threshold
            if age < threshold:
                skipped_age += 1
                continue

            # Safe to cancel
            dispatch.status = "CANCELLED"
            dispatch.sri_status = None
            cancelled += 1
            logger.info(
                "dispatch_cleanup: cancelled orphan dispatch_id=%s order_id=%s "
                "hose_id=%s preset=%s/%s created_at=%s age_seconds=%d threshold=%d",
                dispatch.dispatch_id,
                dispatch.order_id,
                dispatch.hose_id,
                dispatch.preset_type,
                dispatch.preset_value,
                dispatch.created_at.isoformat(),
                age,
                threshold,
            )

        if own_session:
            await db.commit()

        if cancelled:
            logger.warning(
                "dispatch_cleanup: cancelled %d orphan dispatches "
                "(skipped %d active + %d too-young of %d total candidates)",
                cancelled, skipped_active, skipped_age, len(candidates),
            )

        return cancelled

    finally:
        if own_session:
            await db.close()


async def run_cleanup_loop() -> None:
    """
    Infinite background loop. Runs _cancel_orphan_dispatches every
    CLEANUP_INTERVAL_SECONDS. Designed to be started as an asyncio Task
    in the FastAPI lifespan.
    """
    logger.info(
        "dispatch_cleanup: started (interval=%ds, full_age=%ds, preset_age=%ds)",
        CLEANUP_INTERVAL_SECONDS,
        ORPHAN_AGE_FULL,
        ORPHAN_AGE_PRESET,
    )

    while True:
        try:
            cancelled = await _cancel_orphan_dispatches()
            if cancelled:
                logger.info(
                    "dispatch_cleanup: cycle completed — %d cancelled", cancelled
                )
        except Exception:
            logger.exception("dispatch_cleanup: error during cleanup cycle")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


async def get_orphan_count(db: AsyncSession | None = None) -> int:
    """Return the number of orphan dispatches currently pending cleanup."""
    own_session = db is None

    if own_session:
        db = async_session()

    try:
        result = await db.execute(
            select(Dispatch).where(
                Dispatch.status == "AUTHORIZED",
                Dispatch.total == 0.00,
            )
        )
        candidates = result.scalars().all()
        now = datetime.now(ECUADOR_TZ)
        count = 0
        for d in candidates:
            threshold = _orphan_threshold(d)
            age = (now - d.created_at).total_seconds()
            if age >= threshold:
                count += 1
        return count
    finally:
        if own_session:
            await db.close()
