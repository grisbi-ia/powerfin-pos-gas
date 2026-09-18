"""Tests for the PENDING-invoice retry (background scheduler + key refresh).

The retry must:
  * resend same-day invoices as-is (no key churn),
  * regenerate the access key when the retry crosses midnight (Key49 rejects
    past issue dates -> HTTP 400 INVALID_ISSUE_DATE),
  * NOT auto re-date rows older than the configured window (leave them PENDING
    for manual re-emission, never silently FAILED),
  * be a no-op when key49_enabled / sri_retry_enabled are false.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.config import ECUADOR_TZ
from app.models.company import CompanyInfo, SystemConfig
from app.models.dispatch import Dispatch
from app.models.shift import Shift
from app.services import key49_service
from app.services.key49_service import (
    access_key_is_for_today,
    retry_pending_invoices,
)

TODAY = datetime.now(ECUADOR_TZ).strftime("%d%m%Y")
YESTERDAY = (datetime.now(ECUADOR_TZ) - timedelta(days=1)).strftime("%d%m%Y")


def _key_on(date_str: str, sequential: int = 123) -> str:
    """Build a 49-char access key whose first 8 digits are DDMMAAAA."""
    return f"{date_str}" + "0" * 32 + str(sequential).zfill(9)


async def _mk_pending(db, *, created_at, access_key, order="RETRY-1", key49_id=None,
                      status="COLLECTED"):
    shift = Shift(user_id=1, opening_cash=Decimal("0.00"), status="OPEN")
    db.add(shift)
    await db.flush()
    d = Dispatch(
        order_id=order,
        shift_id=shift.shift_id,
        dispenser_id=1,
        emission_point_id=1,
        dispatch_type_id=1,
        person_id=1,
        status=status,
        sri_status="PENDING",
        key49_invoice_id=key49_id,
        access_key=access_key,
        sequential_number="003-501-000000123",
        total=Decimal("10.00"),
        created_at=created_at,
    )
    db.add(d)
    await db.flush()
    return d


@pytest_asyncio.fixture
async def company_ready(db):
    """Key regeneration needs ruc + sri_environment on CompanyInfo."""
    company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one()
    company.ruc = "1790012345001"
    company.sri_environment = 2
    company.emission_type = 1
    await db.flush()


@pytest.fixture
def fake_emit(monkeypatch):
    """Replace the real Key49 POST with a recorder."""
    calls: list[int] = []

    async def _fake(db, dispatch_id):
        calls.append(dispatch_id)
        return True

    monkeypatch.setattr(key49_service, "emitir_factura", _fake)
    return calls


async def _reload(db, dispatch_id) -> Dispatch:
    row = (
        await db.execute(select(Dispatch).where(Dispatch.dispatch_id == dispatch_id))
    ).scalar_one()
    await db.refresh(row)
    return row


# ── access key helpers ─────────────────────────────────────

def test_access_key_is_for_today():
    assert access_key_is_for_today(_key_on(TODAY)) is True
    assert access_key_is_for_today(_key_on(YESTERDAY)) is False
    assert access_key_is_for_today(None) is False
    assert access_key_is_for_today("") is False
    assert access_key_is_for_today("1234567") is False  # too short


# ── retry behaviour ────────────────────────────────────────

@pytest.mark.asyncio
async def test_same_day_resends_without_regenerating(db, fake_emit):
    d = await _mk_pending(
        db,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(minutes=5),
        access_key=_key_on(TODAY),
    )
    await db.commit()
    original_key = d.access_key

    result = await retry_pending_invoices(db)

    assert result["retried"] == 1
    assert result["regenerated"] == 0
    assert fake_emit == [d.dispatch_id]
    assert (await _reload(db, d.dispatch_id)).access_key == original_key


@pytest.mark.asyncio
async def test_cross_midnight_regenerates_key(db, fake_emit, company_ready):
    d = await _mk_pending(
        db,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(hours=20),
        access_key=_key_on(YESTERDAY),
    )
    await db.commit()
    old_key = d.access_key

    result = await retry_pending_invoices(db)

    assert result["retried"] == 1
    assert result["regenerated"] == 1
    assert fake_emit == [d.dispatch_id]
    row = await _reload(db, d.dispatch_id)
    assert row.access_key != old_key
    assert access_key_is_for_today(row.access_key)


@pytest.mark.asyncio
async def test_too_old_left_pending_not_failed(db, fake_emit):
    d = await _mk_pending(
        db,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(days=10),
        access_key=_key_on(YESTERDAY),
    )
    await db.commit()

    result = await retry_pending_invoices(db)

    assert result["expired"] == 1
    assert result["retried"] == 0
    assert fake_emit == []
    assert (await _reload(db, d.dispatch_id)).sri_status == "PENDING"


@pytest.mark.asyncio
async def test_regeneration_failure_is_visible_and_skipped(db, fake_emit, company_ready):
    # Break the company data so the key cannot be regenerated.
    company = (await db.execute(select(CompanyInfo).limit(1))).scalar_one()
    company.sri_environment = None
    d = await _mk_pending(
        db,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(hours=20),
        access_key=_key_on(YESTERDAY),
    )
    await db.commit()

    result = await retry_pending_invoices(db)

    assert result["skipped"] == 1
    assert result["retried"] == 0
    assert fake_emit == []
    row = await _reload(db, d.dispatch_id)
    assert row.sri_status == "PENDING"
    assert "regenerar la clave" in row.sri_messages


@pytest.mark.asyncio
async def test_in_progress_authorized_is_not_retried(db, fake_emit):
    # A freshly created dispatch is AUTHORIZED with sri_status defaulting to
    # PENDING (create_dispatch never sets it). It must NOT be invoiced before
    # the fuel is dispensed and paid.
    await _mk_pending(
        db,
        status="AUTHORIZED",
        created_at=datetime.now(ECUADOR_TZ) - timedelta(minutes=30),
        access_key=_key_on(TODAY),
    )
    await db.commit()

    result = await retry_pending_invoices(db)

    assert result["retried"] == 0
    assert fake_emit == []


@pytest.mark.asyncio
async def test_too_young_collected_is_skipped(db, fake_emit):
    # The live post-collect emission gets a head start (RETRY_MIN_AGE_SECONDS).
    await _mk_pending(
        db,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(seconds=30),
        access_key=_key_on(TODAY),
    )
    await db.commit()

    result = await retry_pending_invoices(db)

    assert result["retried"] == 0
    assert fake_emit == []


@pytest.mark.asyncio
async def test_rows_with_key49_ref_are_not_retried(db, fake_emit):
    await _mk_pending(
        db,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(minutes=5),
        access_key=_key_on(TODAY),
        key49_id="k49-existing",
    )
    await db.commit()

    result = await retry_pending_invoices(db)

    assert result["retried"] == 0
    assert fake_emit == []


@pytest.mark.asyncio
async def test_disabled_flags_are_noops(db, fake_emit):
    await _mk_pending(
        db,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(minutes=5),
        access_key=_key_on(TODAY),
    )
    retry_cfg = SystemConfig(key="sri_retry_enabled", value="false")
    db.add(retry_cfg)
    await db.commit()

    result = await retry_pending_invoices(db)
    assert result["retried"] == 0
    assert fake_emit == []

    # Re-enable retry but disable Key49 entirely.
    retry_cfg.value = "true"
    key49_cfg = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "key49_enabled"))
    ).scalar_one()
    key49_cfg.value = "false"
    await db.flush()
    await db.commit()

    result = await retry_pending_invoices(db)
    assert result["retried"] == 0
    assert fake_emit == []
