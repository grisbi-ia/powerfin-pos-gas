"""
Background cleanup of orphan AUTHORIZED dispatches.

When the Wayne ATO (Authorization Time Out) expires, the dispenser
cancels internally and returns to IDLE, but the POS Backend is never
notified. This leaves an AUTHORIZED + $0.00 dispatch that blocks the
hose indefinitely, requiring manual SQL intervention.

This service runs every 60 seconds and cancels dispatches that:
  - status == 'AUTHORIZED'
  - total == 0.00
  - created more than 900 seconds ago (15 min — safe for large truck fill-ups)

All cancellations are logged for audit trail.

Functions accept an optional db session for testing; when omitted they
create their own session via the app's global async_session factory.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ECUADOR_TZ
from app.database import async_session
from app.models.dispatch import Dispatch

logger = logging.getLogger("pos.cleanup")

# ── Configuration ──────────────────────────────────────────
CLEANUP_INTERVAL_SECONDS = 60  # How often to scan for orphans
ORPHAN_AGE_SECONDS = 900       # Min age before cancelling (15 min — covers large truck fill-ups)
# ───────────────────────────────────────────────────────────


async def _cancel_orphan_dispatches(db: AsyncSession | None = None) -> int:
    """
    Find and cancel AUTHORIZED $0.00 dispatches older than threshold.
    Accepts an optional db session for testing.
    Returns the number of dispatches cancelled.
    """
    cutoff = datetime.now(ECUADOR_TZ) - timedelta(seconds=ORPHAN_AGE_SECONDS)
    own_session = db is None

    if own_session:
        db = async_session()

    try:
        # ── Find orphans ────────────────────────────────────
        result = await db.execute(
            select(Dispatch).where(
                Dispatch.status == "AUTHORIZED",
                Dispatch.total == 0.00,
                Dispatch.created_at < cutoff,
            )
        )
        orphans = result.scalars().all()

        if not orphans:
            return 0

        # ── Cancel each orphan ──────────────────────────────
        cancelled = 0
        for dispatch in orphans:
            dispatch.status = "CANCELLED"
            dispatch.sri_status = None  # Never send cancelled to SRI
            cancelled += 1
            logger.info(
                "dispatch_cleanup: cancelled orphan dispatch_id=%s order_id=%s "
                "hose_id=%s created_at=%s age_seconds=%d",
                dispatch.dispatch_id,
                dispatch.order_id,
                dispatch.hose_id,
                dispatch.created_at.isoformat(),
                int((datetime.now(ECUADOR_TZ) - dispatch.created_at).total_seconds()),
            )

        if own_session:
            await db.commit()

        if cancelled:
            logger.warning(
                "dispatch_cleanup: cancelled %d orphan dispatches "
                "(AUTHORIZED + $0.00, age > %d seconds — likely ATO timeout)",
                cancelled,
                ORPHAN_AGE_SECONDS,
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
        "dispatch_cleanup: started (interval=%ds, orphan_age=%ds)",
        CLEANUP_INTERVAL_SECONDS,
        ORPHAN_AGE_SECONDS,
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
    cutoff = datetime.now(ECUADOR_TZ) - timedelta(seconds=ORPHAN_AGE_SECONDS)
    own_session = db is None

    if own_session:
        db = async_session()

    try:
        result = await db.execute(
            select(Dispatch).where(
                Dispatch.status == "AUTHORIZED",
                Dispatch.total == 0.00,
                Dispatch.created_at < cutoff,
            )
        )
        return len(result.scalars().all())
    finally:
        if own_session:
            await db.close()
