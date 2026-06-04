"""Pydantic schemas for request/response validation."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ── Auth ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    pin: str


class UserResponse(BaseModel):
    user_id: int
    name: str
    role: str
    location_id: int = 1
    location_name: str = "NEOGAS"

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    expires_in: int
    user: UserResponse


# ── Config ───────────────────────────────────────────────────────

class LocationResponse(BaseModel):
    location_id: int
    name: str
    address: Optional[str] = None


class HoseResponse(BaseModel):
    hose_id: int
    fusion_pump_id: int
    fusion_hose_id: int
    grade_id: str
    grade_name: str
    unit_price: float = 0


class DispenserConfigResponse(BaseModel):
    dispenser_id: int
    fusion_pump_id: int
    name: str
    printer_island: int
    sides: dict[str, list[HoseResponse]]


class GradeResponse(BaseModel):
    grade_id: str
    name: str
    unit: str


class PriceListResponse(BaseModel):
    code: str
    name: str


class PaymentMethodResponse(BaseModel):
    code: str
    name: str
    requires_reference: bool


class PollingConfig(BaseModel):
    interval_ms: int = 2000
    enabled: bool = True


class ConfigResponse(BaseModel):
    location: LocationResponse
    dispensers: list[DispenserConfigResponse]
    grades: list[GradeResponse]
    price_lists: list[PriceListResponse]
    payment_methods: list[PaymentMethodResponse]
    polling: PollingConfig


# ── Vehicles ─────────────────────────────────────────────────────

class VehicleOwner(BaseModel):
    customer_id: str
    id_type: str
    id_number: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class VehicleResponse(BaseModel):
    plate: str
    vehicle_found: bool
    incomplete_fields: list[str] = []
    owner: Optional[VehicleOwner] = None
    price_list: str = "STANDARD"
    price_list_name: str = "Precio Normal"


# ── Customers / Persons ──────────────────────────────────────────

class CustomerResponse(BaseModel):
    customer_id: str
    id_type: str
    id_number: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    price_list: str = "STANDARD"
    price_list_name: str = "Precio Normal"
    credit_active: bool = False
    credit_balance: Decimal = Decimal("0")
    plates: list[str] = []


class CreateCustomerRequest(BaseModel):
    id_type: str
    id_number: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    plate: Optional[str] = None


class CreateCustomerResponse(BaseModel):
    customer_id: str
    price_list: str = "STANDARD"


class UpdatePersonRequest(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    price_list_id: Optional[int] = None
    yalobox_wallet: Optional[str] = None


# ── Prices ───────────────────────────────────────────────────────

class PriceResponse(BaseModel):
    grade_id: str
    grade_name: str
    unit_price: Decimal
    price_list: str
    currency: str = "USD"


# ── Shifts ───────────────────────────────────────────────────────

class OpenShiftRequest(BaseModel):
    opening_cash: Decimal = Decimal("0")
    notes: str = ""
    user_name: Optional[str] = None


class ShiftResponse(BaseModel):
    shift_id: int
    user_id: int
    user_name: str
    opened_at: datetime
    accounting_date: str
    status: str
    opening_cash: Decimal

    model_config = {"from_attributes": True}


class CloseShiftRequest(BaseModel):
    closing_cash: Decimal = Decimal("0")
    notes: str = ""


class CloseShiftResponse(BaseModel):
    shift_id: int
    closed_at: datetime
    opening_cash: Decimal
    closing_cash: Decimal
    expected_cash: Decimal
    difference: Decimal
    total_sales: int = 0
    total_volume: Decimal = Decimal("0")
    dispatch_count: int = 0
    accounting_cash_code: Optional[str] = None
    accounting_branch_code: Optional[str] = None


# ── Dispatches ───────────────────────────────────────────────────

class CreateDispatchRequest(BaseModel):
    dispenser_id: int
    hose_id: int
    side: str
    preset_type: str = "MONEY"
    preset_value: str = "0"
    unit_price: Decimal
    payment_method: str = "EFECTIVO"
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    plate: Optional[str] = None
    authorized_by: Optional[str] = None
    dispatch_type_code: str = "SALE"
    credit_contract_id: Optional[int] = None
    items: list["DispatchItemRequest"] = []


class DispatchItemRequest(BaseModel):
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0")


class CreateDispatchResponse(BaseModel):
    order_id: str
    status: str = "PENDING"


class CompleteDispatchRequest(BaseModel):
    order_id: str
    fusion_sale_id: str = ""
    volume: str = "0"
    amount: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    payment_method: str = "EFECTIVO"
    completed_at: Optional[str] = None


class CollectDispatchRequest(BaseModel):
    collected_by_shift_id: int
    payment_method: str = "EFECTIVO"
    collected_amount: Decimal
    change_amount: Decimal = Decimal("0")
    reference_code: Optional[str] = None
    payments: list["PaymentItemRequest"] = []


class PaymentItemRequest(BaseModel):
    payment_method_code: str
    amount: Decimal
    reference_code: Optional[str] = None


class CollectDispatchResponse(BaseModel):
    order_id: str
    status: str = "COLLECTED"
    collected_by_shift_id: int
    collected_by_name: str
    payment_method: str
    collected_amount: Decimal
    change_amount: Decimal


class BillingRequest(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None


class InvoiceRequest(BaseModel):
    """Mark a credit dispatch as invoiced."""
    pass


class DispatchResponse(BaseModel):
    order_id: str
    dispenser_id: int
    hose_id: int
    side: str
    grade: str
    preset_type: str
    preset_value: str
    unit_price: Decimal
    payment_method: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    plate: Optional[str] = None
    status: str
    created_at: datetime
    shift_id: int
    authorized_by: Optional[str] = None
    final_amount: Optional[Decimal] = None
    final_volume: Optional[str] = None
    invoice_number: Optional[str] = None
    credit_contract_id: Optional[int] = None
    credit_status: Optional[str] = None


# ── Cash Movements ───────────────────────────────────────────────

class CreateCashMovementRequest(BaseModel):
    shift_id: int
    type: str  # INCOME, EXPENSE
    amount: Decimal
    observation: str = ""


class CashMovementResponse(BaseModel):
    movement_id: int
    shift_id: int
    type: str
    amount: Decimal
    observation: Optional[str] = None
    created_at: datetime
    running_balance: Decimal


class CashSummaryResponse(BaseModel):
    shift_id: int
    opening_cash: Decimal
    current_balance: Decimal
    total_income: Decimal
    total_expense: Decimal
    total_sales_cash: Decimal
    total_transfers_received: Decimal = Decimal("0")
    total_transfers_sent: Decimal = Decimal("0")
    total_safe_drops: Decimal = Decimal("0")


# ── Transfers ────────────────────────────────────────────────────

class CreateTransferRequest(BaseModel):
    from_shift_id: int
    to_user_id: int
    amount: Decimal
    observation: str = ""


class TransferResponse(BaseModel):
    transfer_id: int
    from_shift_id: int
    from_user_name: str
    to_user_id: int
    to_user_name: str
    amount: Decimal
    observation: Optional[str] = None
    created_at: datetime


# ── Users Online ─────────────────────────────────────────────────

class OnlineUserResponse(BaseModel):
    user_id: int
    name: str
    role: str
    shift_id: int
    sales_count: int = 0
    total_amount: Decimal = Decimal("0")


# ── Credit Contracts ─────────────────────────────────────────────

class CreditContractProductRequest(BaseModel):
    product_id: int
    amount: Decimal


class CreditContractVehicleRequest(BaseModel):
    vehicle_id: int
    date_from: date
    date_to: Optional[date] = None


class CreateCreditContractRequest(BaseModel):
    contract_code: str
    person_id: int
    contract_date: date
    cupo: Decimal
    contract_type: str  # INDEFINIDO, NO_INDEFINIDO
    sercop_type: str = "NO_DEFINIDO"
    notes: Optional[str] = None
    vehicles: list[CreditContractVehicleRequest] = []
    products: list[CreditContractProductRequest] = []


class CreditContractResponse(BaseModel):
    contract_id: int
    contract_code: str
    person_id: int
    person_name: str
    contract_date: date
    cupo: Decimal
    contract_type: str
    sercop_type: str
    notes: Optional[str] = None
    is_active: bool
    vehicles: list["CreditContractVehicleResponse"] = []
    products: list["CreditContractProductResponse"] = []
    available: Optional[Decimal] = None


class CreditContractVehicleResponse(BaseModel):
    contract_vehicle_id: int
    vehicle_id: int
    plate: str
    date_from: date
    date_to: Optional[date] = None
    is_active: bool


class CreditContractProductResponse(BaseModel):
    contract_product_id: int
    product_id: int
    product_code: str
    product_name: str
    amount: Decimal


class CreditContractAvailableResponse(BaseModel):
    contract_id: int
    contract_code: str
    cupo: Decimal
    consumed: Decimal
    available: Decimal
    contract_type: str


class UpdateCreditContractRequest(BaseModel):
    cupo: Optional[Decimal] = None
    contract_type: Optional[str] = None
    sercop_type: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


# ── Products / Categories / Dispatch Types ───────────────────────

class ProductResponse(BaseModel):
    product_id: int
    code: str
    name: str
    category_id: int
    category_name: str
    unit: str
    base_price: Decimal
    is_fuel: bool
    is_active: bool


class ProductCategoryResponse(BaseModel):
    category_id: int
    code: str
    name: str
    is_fuel: bool


class DispatchTypeResponse(BaseModel):
    dispatch_type_id: int
    code: str
    name: str
    requires_customer: bool
    affects_cash: bool


# ── Error ────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
