"""Credit contract validation and cupo disponible calculation."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import CreditContract, CreditContractProduct, CreditContractVehicle
from app.models.dispatch import Dispatch, DispatchDetail


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
        .order_by(CreditContract.contract_type.desc())  # NO_INDEFINIDO first
        .limit(1)
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

    Only COLLECTED dispatches count (authorized/not-yet-completed don't block cupo).

    INDEFINIDO:  cupo - sum(despachos COLLECTED + PENDING_PAYMENT)
    NO_INDEFINIDO: cupo - sum(ALL despachos COLLECTED)
    """
    base_query = select(func.coalesce(func.sum(Dispatch.total), 0)).where(
        Dispatch.credit_contract_id == contract.contract_id,
        Dispatch.status == "COLLECTED",
    )

    if contract.contract_type == "INDEFINIDO":
        base_query = base_query.where(
            Dispatch.credit_status == "PENDING_PAYMENT"
        )

    result = await db.execute(base_query)
    consumed = result.scalar_one() or Decimal("0")
    disponible = contract.cupo - consumed
    return max(disponible, Decimal("0"))


async def calcular_cupo_disponible_por_producto(
    db: AsyncSession, contract_id: int, product_id: int
) -> Decimal:
    """
    Calculate available credit for a specific product within a contract.

    Returns the allocated amount minus consumed dispatches for that product.
    Uses the same logic as calcular_cupo_disponible but scoped to one product.
    """
    allocated = await get_contract_product_amount(db, contract_id, product_id)
    if allocated is None:
        return Decimal("0")

    contract_result = await db.execute(
        select(CreditContract).where(CreditContract.contract_id == contract_id)
    )
    contract = contract_result.scalar_one_or_none()

    base_query = select(func.coalesce(func.sum(Dispatch.total), 0)).where(
        Dispatch.credit_contract_id == contract_id,
        Dispatch.status == "COLLECTED",
    )

    # Scope to product via join on dispatch_details
    base_query = base_query.join(
        DispatchDetail,
        DispatchDetail.dispatch_id == Dispatch.dispatch_id
    ).where(
        DispatchDetail.product_id == product_id
    )

    if contract and contract.contract_type == "INDEFINIDO":
        base_query = base_query.where(
            Dispatch.credit_status == "PENDING_PAYMENT"
        )

    result = await db.execute(base_query)
    consumed = result.scalar_one() or Decimal("0")
    disponible = allocated - consumed
    return max(disponible, Decimal("0"))


async def validate_credit_dispatch(
    db: AsyncSession,
    vehicle_id: int,
    product_id: int,
    amount: Decimal,
) -> tuple[CreditContract, Decimal]:
    """
    Full validation for a credit dispatch.
    Returns (contract, effective_amount) where effective_amount ≤ amount.

    If the requested amount exceeds available credit, it is auto-capped
    to the available balance (both product-level and contract-level).

    Raises CreditValidationError only if:
    - No active contract for the vehicle
    - Product is not allocated in the contract
    - Available balance is $0.00 (fully consumed)
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

    # 3. Validate product-level available balance
    product_available = await calcular_cupo_disponible_por_producto(
        db, contract.contract_id, product_id
    )
    if product_available <= Decimal("0"):
        raise CreditValidationError(
            f"Cupo agotado para este producto. "
            f"No queda saldo disponible."
        )
    if amount > product_available:
        raise CreditValidationError(
            f"Cupo insuficiente para este producto. "
            f"Disponible: ${product_available:,.2f}, Solicitado: ${amount:,.2f}"
        )

    # 4. Validate total contract balance
    total_available = await calcular_cupo_disponible(db, contract)
    if total_available <= Decimal("0"):
        raise CreditValidationError(
            f"Cupo total del contrato agotado. "
            f"No queda saldo disponible."
        )
    if amount > total_available:
        raise CreditValidationError(
            f"Cupo total del contrato insuficiente. "
            f"Disponible: ${total_available:,.2f}, Solicitado: ${amount:,.2f}"
        )

    return contract, amount
