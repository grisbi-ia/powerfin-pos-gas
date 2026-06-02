"""Aggregated model imports — import from app.models to access all models."""

from app.database import Base
from app.models.company import CompanyInfo, SystemConfig
from app.models.credit import CreditContract, CreditContractProduct, CreditContractVehicle
from app.models.dispatch import (
    CashMovement,
    Dispatch,
    DispatchDetail,
    DispatchPayment,
    DispatchType,
    Transfer,
)
from app.models.dispenser import Dispenser, Hose
from app.models.payment import PaymentMethod
from app.models.person import Person, Vehicle
from app.models.pricing import PriceList, PriceListItem
from app.models.product import Grade, Product, ProductCategory, TaxType
from app.models.shift import Shift
from app.models.tributary import EmissionPoint
from app.models.user import Role, User

__all__ = [
    "Base",
    "CashMovement",
    "CompanyInfo",
    "CreditContract",
    "CreditContractProduct",
    "CreditContractVehicle",
    "Dispatch",
    "DispatchDetail",
    "DispatchPayment",
    "DispatchType",
    "Dispenser",
    "EmissionPoint",
    "Grade",
    "Hose",
    "PaymentMethod",
    "Person",
    "PriceList",
    "PriceListItem",
    "Product",
    "ProductCategory",
    "Role",
    "Shift",
    "SystemConfig",
    "TaxType",
    "Transfer",
    "User",
    "Vehicle",
]
