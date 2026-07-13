"""Tests for orphan dispatch cleanup service."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, text as sa_text

from app.config import ECUADOR_TZ
from app.models.dispatch import Dispatch
from app.services.dispatch_cleanup import (
    _cancel_orphan_dispatches,
    get_orphan_count,
    ORPHAN_AGE_SECONDS,
)


@pytest.mark.asyncio
async def test_no_orphans_when_none_exist(db):
    """get_orphan_count returns 0 when no orphans exist."""
    count = await get_orphan_count(db=db)
    assert count == 0


@pytest.mark.asyncio
async def test_cancel_orphans_returns_zero_when_none_exist(db):
    """_cancel_orphan_dispatches returns 0 when nothing to cancel."""
    cancelled = await _cancel_orphan_dispatches(db=db)
    assert cancelled == 0


@pytest.mark.asyncio
async def test_orphan_not_cancelled_when_too_recent(db):
    """AUTHORIZED + $0.00 dispatch created just now should NOT be cancelled."""
    await db.execute(
        sa_text("INSERT INTO shifts (shift_id, user_id, opening_cash, status, accounting_date) "
                "VALUES (100, 1, 0.00, 'OPEN', CURRENT_DATE)")
    )
    await db.flush()

    await db.execute(
        sa_text("""
            INSERT INTO dispatches (order_id, shift_id, dispenser_id, hose_id,
                grade_id, dispatch_type_id, subtotal, tax_amount, total, status,
                preset_type, preset_value, created_at, authorized_by_user_id)
            VALUES ('OV-TEST-RECENT-001', 100, 1, 1,
                'DIESEL', 1, 0.00, 0.00, 0.00, 'AUTHORIZED',
                'MONEY', '0', NOW(), 1)
        """)
    )
    await db.commit()

    count = await get_orphan_count(db=db)
    assert count == 0  # Too recent, under ORPHAN_AGE_SECONDS threshold

    cancelled = await _cancel_orphan_dispatches(db=db)
    assert cancelled == 0  # Nothing cancelled


@pytest.mark.asyncio
async def test_orphan_cancelled_when_old_enough(db):
    """AUTHORIZED + $0.00 dispatch old enough should be cancelled."""
    old_time = datetime.now(ECUADOR_TZ) - timedelta(seconds=ORPHAN_AGE_SECONDS + 60)

    await db.execute(
        sa_text("INSERT INTO shifts (shift_id, user_id, opening_cash, status, accounting_date) "
                "VALUES (101, 1, 0.00, 'OPEN', CURRENT_DATE)")
    )
    await db.flush()

    await db.execute(
        sa_text("""
            INSERT INTO dispatches (order_id, shift_id, dispenser_id, hose_id,
                grade_id, dispatch_type_id, subtotal, tax_amount, total, status,
                preset_type, preset_value, created_at, authorized_by_user_id)
            VALUES ('OV-TEST-OLD-001', 101, 1, 1,
                'DIESEL', 1, 0.00, 0.00, 0.00, 'AUTHORIZED',
                'MONEY', '20', :created_at, 1)
        """),
        {"created_at": old_time},
    )
    await db.commit()

    # Should appear as orphan
    count = await get_orphan_count(db=db)
    assert count == 1

    # Should be cancelled
    cancelled = await _cancel_orphan_dispatches(db=db)
    assert cancelled == 1

    # Verify it's now CANCELLED
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == "OV-TEST-OLD-001")
    )
    dispatch = result.scalar_one()
    assert dispatch.status == "CANCELLED"
    assert dispatch.sri_status is None  # Never goes to SRI

    # Count should now be 0
    count = await get_orphan_count(db=db)
    assert count == 0


@pytest.mark.asyncio
async def test_completed_with_amount_not_cancelled(db):
    """COMPLETED dispatch with real amount should NEVER be auto-cancelled."""
    old_time = datetime.now(ECUADOR_TZ) - timedelta(seconds=ORPHAN_AGE_SECONDS + 60)

    await db.execute(
        sa_text("INSERT INTO shifts (shift_id, user_id, opening_cash, status, accounting_date) "
                "VALUES (102, 1, 0.00, 'OPEN', CURRENT_DATE)")
    )
    await db.flush()

    await db.execute(
        sa_text("""
            INSERT INTO dispatches (order_id, shift_id, dispenser_id, hose_id,
                grade_id, dispatch_type_id, subtotal, tax_amount, total, status,
                preset_type, preset_value, created_at, authorized_by_user_id)
            VALUES ('OV-TEST-COMPLETED-001', 102, 1, 1,
                'DIESEL', 1, 8.70, 1.30, 10.00, 'COMPLETED',
                'MONEY', '10', :created_at, 1)
        """),
        {"created_at": old_time},
    )
    await db.commit()

    cancelled = await _cancel_orphan_dispatches(db=db)
    assert cancelled == 0  # COMPLETED with amount > 0 must NOT be cancelled

    # Verify untouched
    result = await db.execute(
        select(Dispatch).where(Dispatch.order_id == "OV-TEST-COMPLETED-001")
    )
    dispatch = result.scalar_one()
    assert dispatch.status == "COMPLETED"
