"""Unit tests: 'RUC Proveedor' in Key49 invoice additional_info.

SRI requires the invoicing software provider's RUC (GRISBI) on EVERY
invoice sent to Key49 — individual and global (bulk/public sector).
Value source: system_config key 'powerfin_system_provider_ruc'.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.company import CompanyInfo, SystemConfig
from app.models.dispatch import Dispatch, DispatchDetail
from app.models.shift import Shift
from app.services.key49_service import _build_invoice_payload, emitir_factura_global


async def _insert_dispatch(db) -> Dispatch:
    """Insert a minimal valid dispatch (individual sale) + details."""
    shift = Shift(user_id=1, opening_cash=Decimal("0.00"), status="OPEN")
    db.add(shift)
    await db.flush()

    d = Dispatch(
        order_id="OV-TEST-RUC",
        shift_id=shift.shift_id,
        dispenser_id=1,
        emission_point_id=1,
        dispatch_type_id=1,
        person_id=1,
        sequential_number="001-001-000000042",
        access_key="1234567890123456789012345678901234567890123456789",
        subtotal=Decimal("50.00"),
        tax_amount=Decimal("7.50"),
        total=Decimal("57.50"),
        preset_type="MONEY",
        status="COLLECTED",
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
    return d


class TestProviderRucIndividual:
    @pytest.mark.asyncio
    async def test_payload_includes_provider_ruc(self, db):
        """RUC Proveedor present with value from system_config."""
        d = await _insert_dispatch(db)
        payload = await _build_invoice_payload(db, d)
        assert payload is not None
        assert payload["additional_info"]["RUC Proveedor"] == "0190411826001"

    @pytest.mark.asyncio
    async def test_keeps_existing_additional_info_fields(self, db):
        """order_id + placa still present alongside RUC Proveedor."""
        d = await _insert_dispatch(db)
        payload = await _build_invoice_payload(db, d)
        info = payload["additional_info"]
        assert info["order_id"] == "OV-TEST-RUC"
        assert "placa" in info
        assert "RUC Proveedor" in info

    @pytest.mark.asyncio
    async def test_empty_when_config_key_missing(self, db):
        """Field is sent (not silently omitted) even if key is missing."""
        cfg = (await db.execute(
            select(SystemConfig).where(
                SystemConfig.key == "powerfin_system_provider_ruc"
            )
        )).scalar_one()
        await db.delete(cfg)
        await db.commit()

        d = await _insert_dispatch(db)
        payload = await _build_invoice_payload(db, d)
        # Key49/SRI will surface the missing value — never dropped silently
        assert payload["additional_info"]["RUC Proveedor"] == ""


class _FakeResp:
    status_code = 202

    def json(self):
        return {"data": {"id": "k49-global-1"}}


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
        return _FakeResp()


class TestProviderRucGlobal:
    """Bulk / public-sector (GAD PAUTE) global invoice."""

    @pytest.mark.asyncio
    async def test_global_payload_includes_provider_ruc(self, db, monkeypatch):
        monkeypatch.setattr("httpx.AsyncClient", _FakeClient)
        _FakeClient.captured = {}

        shift = Shift(user_id=1, opening_cash=Decimal("0.00"), status="OPEN")
        db.add(shift)
        await db.flush()

        d = Dispatch(
            order_id="OV-GLOBAL-1",
            shift_id=shift.shift_id,
            dispenser_id=1,
            emission_point_id=1,
            dispatch_type_id=1,
            person_id=2,  # RUC entity (public sector)
            credit_contract_id=2,  # NO_INDEFINIDO contract from seed
            credit_status="PENDING_BULK_INVOICE",
            sequential_number="001-001-000000043",
            access_key="1234567890123456789012345678901234567890123456789",
            subtotal=Decimal("50.00"),
            tax_amount=Decimal("7.50"),
            total=Decimal("57.50"),
            preset_type="MONEY",
            status="COLLECTED",
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

        company = (await db.execute(
            select(CompanyInfo).limit(1)
        )).scalar_one()
        ep = (await db.execute(
            select(Dispatch.emission_point_id).where(
                Dispatch.dispatch_id == d.dispatch_id
            )
        )).scalar_one()

        from app.models.tributary import EmissionPoint
        ep_obj = (await db.execute(
            select(EmissionPoint).where(EmissionPoint.emission_point_id == ep)
        )).scalar_one()

        result = await emitir_factura_global(
            db, 2, [d.dispatch_id],
            access_key=d.access_key,
            sequential_number="001-001-000000043",
            ep=ep_obj,
            company=company,
        )

        assert result.get("errors") == []
        payload = _FakeClient.captured["json"]
        info = payload["additional_info"]
        assert info["RUC Proveedor"] == "0190411826001"
        assert info["contract_code"] == "CT-PUB-001"
        assert info["contract_type"] == "SECTOR_PUBLICO"
