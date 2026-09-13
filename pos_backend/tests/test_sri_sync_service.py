"""Tests for the SRI/Key49 background reconciler (non-final → synced).

The reconciler must only touch NON-FINAL rows that already have a Key49
reference, be inert while disabled, and avoid hammering Key49 for rows that
stay stalled (REJECTED/FAILED).
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.config import ECUADOR_TZ
from app.models.company import SystemConfig
from app.models.dispatch import Dispatch
from app.models.shift import Shift
from app.services import sri_sync_service
from app.services.sri_sync_service import sync_non_final_dispatches


class _FakeResp:
    status_code = 200

    def __init__(self, status="NOTIFIED"):
        self._status = status

    def json(self):
        return {"data": {
            "id": "k49-1",
            "status": self._status,
            "access_key": "1109202601099323083900120035010000045909976527418",
            "authorization_date": "2026-09-11T21:44:00.626564Z",
            "sri_messages": [],
        }}


class _FakeClient:
    calls: list = []
    status = "NOTIFIED"

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        _FakeClient.calls.append(url)
        return _FakeResp(_FakeClient.status)


@pytest.fixture(autouse=True)
def _reset_cooldown():
    sri_sync_service.reset_stalled_recheck_tracker()
    _FakeClient.calls = []
    _FakeClient.status = "NOTIFIED"
    yield
    sri_sync_service.reset_stalled_recheck_tracker()


async def _mk_dispatch(db, *, key49_id, age_seconds, order="SYNC-1", status="PENDING"):
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
        status="COLLECTED",
        total=Decimal("10.00"),
        sri_status=status,
        key49_invoice_id=key49_id,
        created_at=datetime.now(ECUADOR_TZ) - timedelta(seconds=age_seconds),
    )
    db.add(d)
    await db.flush()
    return d


@pytest.mark.asyncio
async def test_disabled_by_default(db, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    await _mk_dispatch(db, key49_id="k49-1", age_seconds=600)
    await db.commit()

    result = await sync_non_final_dispatches(db)
    assert result["enabled"] is False
    assert _FakeClient.calls == []  # no Key49 calls while disabled


@pytest.mark.asyncio
async def test_reconciles_pending_sent(db, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    db.add(SystemConfig(key="sri_sync_enabled", value="true"))
    d = await _mk_dispatch(db, key49_id="k49-1", age_seconds=600)
    did = d.dispatch_id
    await db.commit()

    result = await sync_non_final_dispatches(db)
    assert result["enabled"] is True
    assert result["updated"] == 1

    row = (await db.execute(select(Dispatch).where(Dispatch.dispatch_id == did))).scalar_one()
    await db.refresh(row)
    assert row.sri_status == "NOTIFIED"
    assert row.sri_authorization_date is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_status", ["RETRY", "RECEIVED", "SENT", "CREATED"])
async def test_reconciles_any_non_final_status(db, monkeypatch, stale_status):
    """A Key49-side change must be picked up from ANY non-final status."""
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    db.add(SystemConfig(key="sri_sync_enabled", value="true"))
    d = await _mk_dispatch(
        db, key49_id="k49-1", age_seconds=600,
        order=f"SYNC-{stale_status}", status=stale_status,
    )
    did = d.dispatch_id
    await db.commit()

    result = await sync_non_final_dispatches(db)
    assert result["updated"] == 1

    row = (await db.execute(select(Dispatch).where(Dispatch.dispatch_id == did))).scalar_one()
    await db.refresh(row)
    assert row.sri_status == "NOTIFIED"


@pytest.mark.asyncio
async def test_reconciles_rejected_after_key49_reprocess(db, monkeypatch):
    """REJECTED -> NOTIFIED (Key49 reprocess) must be picked up."""
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    db.add(SystemConfig(key="sri_sync_enabled", value="true"))
    d = await _mk_dispatch(
        db, key49_id="k49-1", age_seconds=600,
        order="SYNC-REJECTED", status="REJECTED",
    )
    did = d.dispatch_id
    await db.commit()

    result = await sync_non_final_dispatches(db)
    assert result["updated"] == 1

    row = (await db.execute(select(Dispatch).where(Dispatch.dispatch_id == did))).scalar_one()
    await db.refresh(row)
    assert row.sri_status == "NOTIFIED"


@pytest.mark.asyncio
async def test_stalled_rows_are_not_rechecked_every_cycle(db, monkeypatch):
    """A REJECTED row that stays REJECTED is queried at most once per cooldown."""
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    _FakeClient.status = "REJECTED"
    db.add(SystemConfig(key="sri_sync_enabled", value="true"))
    d = await _mk_dispatch(
        db, key49_id="k49-1", age_seconds=600,
        order="SYNC-STALLED", status="REJECTED",
    )
    await db.commit()

    first = await sync_non_final_dispatches(db)
    assert first["scanned"] == 1
    calls_after_first = len(_FakeClient.calls)

    second = await sync_non_final_dispatches(db)
    assert second["scanned"] == 0            # cooldown: skipped
    assert len(_FakeClient.calls) == calls_after_first


@pytest.mark.asyncio
async def test_skips_rows_without_key49_id(db, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    db.add(SystemConfig(key="sri_sync_enabled", value="true"))
    await _mk_dispatch(db, key49_id=None, age_seconds=600, order="SYNC-NOKEY")
    await db.commit()

    result = await sync_non_final_dispatches(db)
    assert _FakeClient.calls == []  # never sent -> never queried
    assert result["updated"] == 0


@pytest.mark.asyncio
async def test_skips_too_young_rows(db, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    db.add(SystemConfig(key="sri_sync_enabled", value="true"))
    await _mk_dispatch(db, key49_id="k49-1", age_seconds=10, order="SYNC-YOUNG")
    await db.commit()

    result = await sync_non_final_dispatches(db)
    assert _FakeClient.calls == []  # live poller still owns it
    assert result["updated"] == 0


@pytest.mark.asyncio
async def test_skips_final_rows(db, monkeypatch):
    """AUTHORIZED/NOTIFIED rows are never queried."""
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
    db.add(SystemConfig(key="sri_sync_enabled", value="true"))
    await _mk_dispatch(
        db, key49_id="k49-1", age_seconds=600,
        order="SYNC-FINAL", status="NOTIFIED",
    )
    await db.commit()

    result = await sync_non_final_dispatches(db)
    assert _FakeClient.calls == []
    assert result["updated"] == 0
