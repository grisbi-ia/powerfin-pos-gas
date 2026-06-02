"""Credit contract validation and cupo disponible calculation."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditContract, CreditContractProduct, CreditContractVehicle
from app.models.dispatch import Dispatch


class CreditValidationError(Exception):
    """Raised when a credit dispatch fails validation."""


async def find_active_contract_for_vehicle(
    db: AsyncSession, vehicle_id: int
) -> CreditContract | None:
    """
    Find an active credit contract that covers the given vehicle
    and is within its valid date range.
    """
    today = date.today()
    result = await db.execute(
        select(CreditContract)
        .join(CreditContractVehicle)
        .where(
            CreditContractVehicle.vehicle_id == vehicle_id,
            CreditContract.is_active == True,
            CreditContractVehicle.is_active == True,
            CreditContractVehicle.date_from <= today,
            or_(
                CreditContractVehicle.date_to.is_(None),
                CreditContractVehicle.date_to >= today,
            ),
        )
    )
    return result.scalar_one_or_none()


async def get_contract_product_amount(
    db: AsyncSession, contract_id: int, product_id: int
) -> Decimal | None:
    """Get the allocated amount for a product within a contract."""
    result = await db.execute(
        select(CreditContractProduct.amount).where(
            CreditContractProduct.contract_id == contract_id,
            CreditContractProduct.product_id == product_id,
        )
    )
    row = result.scalar_one_or_none()
    return Decimal(str(row)) if row else None


async def calcular_cupo_disponible(
    db: AsyncSession, contract: CreditContract
) -> Decimal:
    """
    Calculate available credit for a contract.

    INDEFINIDO:  cupo - sum(dispatches with credit_status='PENDING_INVOICE')
    NO_INDEFINIDO: cupo - sum(ALL dispatches, regardless of invoice status)
    """
    base_query = select(func.coalesce(func.sum(Dispatch.total), 0)).where(
        Dispatch.credit_contract_id == contract.contract_id,
        Dispatch.status != "CANCELLED",
    )

    if contract.contract_type == "INDEFINIDO":
        base_query = base_query.where(
            Dispatch.credit_status == "PENDING_INVOICE"
        )

    result = await db.execute(base_query)
    consumed = result.scalar_one() or Decimal("0")
    return contract.cupo - consumed


async def validate_credit_dispatch(
    db: AsyncSession,
    vehicle_id: int,
    product_id: int,
    amount: Decimal,
) -> CreditContract:
    """
    Full validation for a credit dispatch. Returns the contract if valid.
    Raises CreditValidationError with a user-friendly message on failure.
    """
    # 1. Vehicle must have an active contract
    contract = await find_active_contract_for_vehicle(db, vehicle_id)
    if not contract:
        raise CreditValidationError(
            "El vehículo no tiene un contrato de crédito activo."
        )

    # 2. Product must be allocated in the contract
    product_amount = await get_contract_product_amount(db, contract.contract_id, product_id)
    if product_amount is None:
        raise CreditValidationError(
            "El producto no está asignado al contrato de crédito."
        )

    # 3. Check available credit
    available = await calcular_cupo_disponible(db, contract)
    if amount > available:
        raise CreditValidationError(
            f"Cupo de crédito insuficiente. "
            f"Disponible: ${available:,.2f}, Solicitado: ${amount:,.2f}"
        )

    return contract
