"""Unit test: Key49 HTTP 409 DUPLICATE_DOCUMENT must LINK the existing invoice.

Incident context: after the PLAN_EXPIRED outage, some dispatches were invoiced
at Key49 but our DB never stored the key49_invoice_id (process killed / polling
timeout). Re-emitting them returns 409 with error.existing_document — we must
link that document instead of leaving the dispatch PENDING forever.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.dispatch import Dispatch, DispatchDetail
from app.models.shift import Shift
from app.services.key49_service import emitir_factura


class _FakeResp409:
    status_code = 409
    text = ""

    def json(self):
        return {
            "error": {
                "code": "DUPLICATE_DOCUMENT",
                "message": "Invoice 003-501-000000042 already exists with status NOTIFIED",
                "existing_document": {
                    "id": "existing-uuid-1234",
                    "status": "NOTIFIED",
                    "access_key": "1109202601099323083900120035010000000421472239013",
                    "authorization_date": "2026-09-11T11:45:05.426700Z",
                },
            }
        }


class _FakeClient:
    captured: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        _FakeClient.captured = {"url": url, "json": json, "headers": headers}
        return _FakeResp409()


@pytest.mark.asyncio
async def test_duplicate_409_links_existing_document(db, monkeypatch):
    monkeypatch.setattr("httpx.AsyncClient", _FakeClient)

    shift = Shift(user_id=1, opening_cash=Decimal("0.00"), status="OPEN")
    db.add(shift)
    await db.flush()

    d = Dispatch(
        order_id="OV-DUP-1",
        shift_id=shift.shift_id,
        dispenser_id=1,
        emission_point_id=1,
        dispatch_type_id=1,
        person_id=1,
        sequential_number="001-001-000000042",
        access_key="1" * 49,
        subtotal=Decimal("50.00"),
        tax_amount=Decimal("7.50"),
        total=Decimal("57.50"),
        preset_type="MONEY",
        status="COLLECTED",
        sri_status="PENDING",
        created_at=datetime.now(),
    )
    db.add(d)
    await db.flush()
    db.add(DispatchDetail(
        dispatch_id=d.dispatch_id,
        product_id=1,
        quantity=Decimal("10.0000"),
        unit_price=Decimal("5.0000"),
        tax_rate=Decimal("0.1500"),
        subtotal=Decimal("50.00"),
        total=Decimal("57.50"),
    ))
    await db.flush()
    did = d.dispatch_id

    ok = await emitir_factura(db, did)
    assert ok is True

    row = (await db.execute(
        select(Dispatch).where(Dispatch.dispatch_id == did)
    )).scalar_one()
    await db.refresh(row)
    assert row.key49_invoice_id == "existing-uuid-1234"
    assert row.key49_access_key == "1109202601099323083900120035010000000421472239013"
    assert row.sri_status == "NOTIFIED"
    assert row.sri_authorization_date is not None
    assert row.sri_messages is None
