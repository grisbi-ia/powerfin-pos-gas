"""Unit tests for credit_service."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.credit import CreditContract, CreditContractVehicle
from app.models.dispatch import Dispatch
from app.models.shift import Shift
from app.services.credit_service import (
    CreditValidationError,
    calcular_cupo_disponible,
    find_active_contract_for_vehicle,
    get_contract_product_amount,
    validate_credit_dispatch,
)


async def _make_shift(db):
    s = Shift(shift_id=1, user_id=2, status="OPEN")
    db.add(s)
    await db.flush()
    return s


class TestFindActiveContract:
    @pytest.mark.asyncio
    async def test_finds_contract_for_vehicle(self, db):
        contract = await find_active_contract_for_vehicle(db, 2)
        assert contract is not None
        assert contract.contract_code == "CT-001"

    @pytest.mark.asyncio
    async def test_no_contract_for_vehicle(self, db):
        contract = await find_active_contract_for_vehicle(db, 1)
        assert contract is None

    @pytest.mark.asyncio
    async def test_contract_outside_date_range_not_found(self, db):
        cv = (await db.execute(
            select(CreditContractVehicle).where(CreditContractVehicle.vehicle_id == 2)
        )).scalar_one()
        cv.date_from = date(2020, 1, 1)
        cv.date_to = date(2020, 12, 31)
        await db.flush()
        contract = await find_active_contract_for_vehicle(db, 2)
        assert contract is None


class TestContractProductAmount:
    @pytest.mark.asyncio
    async def test_gets_amount(self, db):
        amount = await get_contract_product_amount(db, 1, 1)
        assert amount == Decimal("3000.00")

    @pytest.mark.asyncio
    async def test_product_not_in_contract(self, db):
        amount = await get_contract_product_amount(db, 1, 2)
        assert amount is None


class TestCupoDisponible:
    @pytest.mark.asyncio
    async def test_indefinido_full_available(self, db):
        available = await calcular_cupo_disponible(
            db,
            CreditContract(
                contract_id=1, cupo=Decimal("5000.00"),
                contract_type="INDEFINIDO"
            )
        )
        assert available == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_indefinido_deducts_pending_invoice(self, db):
        await _make_shift(db)
        db.add(Dispatch(
            order_id="OV-001", shift_id=1, dispenser_id=1,
            dispatch_type_id=1, total=1000.00,
            credit_contract_id=1, credit_status="PENDING_INVOICE",
        ))
        await db.flush()
        contract = (await db.execute(
            select(CreditContract).where(CreditContract.contract_id == 1)
        )).scalar_one()
        available = await calcular_cupo_disponible(db, contract)
        assert available == Decimal("4000.00")

    @pytest.mark.asyncio
    async def test_indefinido_ignores_invoiced(self, db):
        await _make_shift(db)
        db.add(Dispatch(
            order_id="OV-001", shift_id=1, dispenser_id=1,
            dispatch_type_id=1, total=1000.00,
            credit_contract_id=1, credit_status="INVOICED",
        ))
        await db.flush()
        contract = (await db.execute(
            select(CreditContract).where(CreditContract.contract_id == 1)
        )).scalar_one()
        available = await calcular_cupo_disponible(db, contract)
        assert available == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_no_indefinido_deducts_all(self, db):
        await _make_shift(db)
        contract = (await db.execute(
            select(CreditContract).where(CreditContract.contract_id == 1)
        )).scalar_one()
        contract.contract_type = "NO_INDEFINIDO"
        await db.flush()
        db.add(Dispatch(
            order_id="OV-001", shift_id=1, dispenser_id=1,
            dispatch_type_id=1, total=1000.00,
            credit_contract_id=1, credit_status="INVOICED",
        ))
        await db.flush()
        available = await calcular_cupo_disponible(db, contract)
        assert available == Decimal("4000.00")


class TestValidateCreditDispatch:
    @pytest.mark.asyncio
    async def test_valid_dispatch(self, db):
        contract = await validate_credit_dispatch(db, 2, 1, Decimal("500.00"))
        assert contract.contract_code == "CT-001"

    @pytest.mark.asyncio
    async def test_vehicle_not_in_contract(self, db):
        with pytest.raises(CreditValidationError, match="no tiene un contrato"):
            await validate_credit_dispatch(db, 1, 1, Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_product_not_in_contract(self, db):
        with pytest.raises(CreditValidationError, match="no está asignado"):
            await validate_credit_dispatch(db, 2, 2, Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_amount_exceeds_available(self, db):
        with pytest.raises(CreditValidationError, match="insuficiente"):
            await validate_credit_dispatch(db, 2, 1, Decimal("10000.00"))
