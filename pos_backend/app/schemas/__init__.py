"""Pydantic schemas for request/response validation."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, field_validator, model_validator, Field


# ── Auth ─────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    pin: str


class AdminLoginRequest(BaseModel):
    """Admin login uses password (full text), not numeric PIN."""
    username: str
    password: str


class AdminUserInfo(BaseModel):
    user_id: int
    username: str
    name: str
    role: str
    permissions: dict = {}


class AdminLoginResponse(BaseModel):
    access_token: str
    expires_in: int
    user: AdminUserInfo


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
    ruc: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    fiscal_regime: Optional[str] = None
    sri_environment: Optional[int] = None
    emission_type: Optional[int] = None


class HoseResponse(BaseModel):
    hose_id: int
    fusion_pump_id: int
    fusion_hose_id: int
    grade_id: str
    grade_name: str
    unit_price: float = 0
    base_price: float = 0
    subsidy_per_unit: float = 0


class DispenserConfigResponse(BaseModel):
    dispenser_id: int
    name: str
    printer_ip: Optional[str] = None
    printer_port: int = 9100
    sides: dict[str, list[HoseResponse]]


class GradeResponse(BaseModel):
    grade_id: str
    name: str
    unit: str


class PriceListResponse(BaseModel):
    code: str
    name: str


class PaymentMethodResponse(BaseModel):
    payment_method_id: int
    code: str
    name: str
    requires_reference: bool
    sri_code: str = "20"


class PollingConfig(BaseModel):
    interval_ms: int = 2000
    enabled: bool = True


class ConfigResponse(BaseModel):
    location: LocationResponse
    dispensers: list[DispenserConfigResponse]
    grades: list[GradeResponse]
    price_lists: list[PriceListResponse]
    payment_methods: list[PaymentMethodResponse]
    printer_policy: str = "ASK"
    max_cash_in_hand: float = 300.0
    cash_printer_ip: str = ""
    cash_printer_port: int = 9100
    polling: PollingConfig


class StationInfoResponse(BaseModel):
    """Public station info — no auth required (login page)."""
    name: str
    commercial_name: str | None = None


# ── Vehicles ─────────────────────────────────────────────────────

class VehicleOwner(BaseModel):
    person_id: Optional[int] = None
    customer_id: str
    id_type: str
    id_number: str
    name: str
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class VehicleResponse(BaseModel):
    vehicle_id: int
    plate: str
    vehicle_found: bool
    incomplete_fields: list[str] = []
    owner: Optional[VehicleOwner] = None
    billing_person: Optional[VehicleOwner] = None
    price_list: str = "STANDARD"
    price_list_name: str = "Precio Normal"


class SetBillingPersonRequest(BaseModel):
    """Set or clear the preferred billing person for a vehicle."""
    person_id: Optional[int] = None  # None = clear, use owner


class PredefinedVehicleResponse(BaseModel):
    """Vehicle flagged for container sales (customer has no vehicle)."""
    vehicle_id: int
    plate: str
    owner_name: str


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
    notes: str = ""


class CloseShiftResponse(BaseModel):
    shift_id: int
    closed_at: datetime
    opened_at: Optional[datetime] = None
    opening_cash: Decimal
    surplus: Decimal = Decimal("0")
    shortage: Decimal = Decimal("0")
    total_sales: float = 0.0
    total_volume: Decimal = Decimal("0")
    dispatch_count: int = 0
    accounting_cash_code: Optional[str] = None
    # Cash movement breakdown
    cash_income: Decimal = Decimal("0")
    cash_income_count: int = 0
    cash_expense: Decimal = Decimal("0")
    cash_expense_count: int = 0
    cash_deposits: Decimal = Decimal("0")
    cash_deposits_count: int = 0
    cash_transfers_out: Decimal = Decimal("0")
    cash_transfers_out_count: int = 0
    cash_transfers_in: Decimal = Decimal("0")
    cash_transfers_in_count: int = 0
    cash_safe_drops: Decimal = Decimal("0")
    cash_safe_drops_count: int = 0
    # Cash sales
    sales_cash: Decimal = Decimal("0")
    sales_cash_count: int = 0
    # Non-cash sales breakdown
    non_cash_sales: list = []
    accounting_branch_code: Optional[str] = None


# ── Dispatches ───────────────────────────────────────────────────

class CreateDispatchRequest(BaseModel):
    dispenser_id: int
    hose_id: int
    side: str
    preset_type: str = "MONEY"
    preset_value: str = "0"
    unit_price: Decimal
    payment_method_id: int = 1
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
    amount: str = "0"
    unit_price: str = "0"
    payment_method_id: int = 1
    payment_method: Optional[str] = None  # deprecated, kept for backward compat
    completed_at: Optional[str] = None

    @field_validator('amount', 'unit_price', mode='before')
    @classmethod
    def coerce_to_str(cls, v):
        """Accept both JSON numbers (float/int) and strings."""
        if v is None:
            return "0"
        return str(v)

    @field_validator('payment_method', mode='before')
    @classmethod
    def legacy_payment_method(cls, v):
        """Accept legacy payment_method string or int."""
        return v  # just pass through, model_validator handles mapping

    @model_validator(mode='before')
    @classmethod
    def normalize_payment(cls, data: Any) -> Any:
        """Map legacy payment_method to payment_method_id if needed."""
        if isinstance(data, dict):
            # If old format has payment_method but not payment_method_id
            if "payment_method" in data and "payment_method_id" not in data:
                pm = data["payment_method"]
                try:
                    data["payment_method_id"] = int(pm)
                except (ValueError, TypeError):
                    data["payment_method_id"] = 1
            # If both present, remove old field
            if "payment_method" in data and "payment_method_id" in data:
                data.pop("payment_method", None)
        return data


class CompleteByPumpRequest(BaseModel):
    """Complete the AUTHORIZED dispatch for a given pump+hose.
    Fallback when PAY_IN orderId is not echoed by Wayne in PRESET flows."""
    fusion_pump_id: int
    fusion_hose_id: int
    volume: str = "0"
    amount: str = "0"
    unit_price: str = "0"

    @field_validator('amount', 'unit_price', 'volume', mode='before')
    @classmethod
    def coerce_to_str(cls, v):
        """Accept both JSON numbers (float/int) and strings."""
        if v is None:
            return "0"
        return str(v)


class CollectDispatchRequest(BaseModel):
    collected_by_shift_id: int
    payment_method_id: int = 1
    collected_amount: Decimal
    change_amount: Decimal = Decimal("0")
    reference_code: Optional[str] = None
    payments: list["PaymentItemRequest"] = []


class PaymentItemRequest(BaseModel):
    payment_method_id: int
    amount: Decimal
    reference_code: Optional[str] = None


class CollectDispatchResponse(BaseModel):
    order_id: str
    status: str = "COLLECTED"
    collected_by_shift_id: int
    collected_by_name: str
    payment_method_id: int
    collected_amount: Decimal
    change_amount: Decimal
    receipt_data: dict | None = None  # Full data for printing (from DB)


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
    total_deposits: Decimal = Decimal("0")
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
    sender_movement_id: int
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


# ── Admin — Generic ───────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    """Generic wrapper for paginated list endpoints."""
    items: list
    total: int
    page: int
    page_size: int
    pages: int


# ── Admin — Users ─────────────────────────────────────────────────

class AdminUserListItem(BaseModel):
    user_id: int
    username: str
    name: str
    role: str
    role_name: str
    is_active: bool

    model_config = {"from_attributes": True}


class AdminUserDetail(BaseModel):
    user_id: int
    username: str
    name: str
    role_id: int
    role: str
    role_name: str
    accounting_cash_code: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    username: str
    name: str
    password: str = Field(min_length=4, max_length=128)
    role_id: int
    accounting_cash_code: str | None = None
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    name: str | None = None
    password: str | None = Field(default=None, min_length=4, max_length=128)
    role_id: int | None = None
    accounting_cash_code: str | None = None
    is_active: bool | None = None


# ── Admin — Roles ─────────────────────────────────────────────────

class AdminRoleListItem(BaseModel):
    role_id: int
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class AdminRoleDetail(BaseModel):
    role_id: int
    code: str
    name: str
    permissions_json: dict | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CreateRoleRequest(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z_]+$")
    name: str = Field(min_length=2, max_length=100)
    permissions_json: dict | None = None
    is_active: bool = True


class UpdateRoleRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    permissions_json: dict | None = None
    is_active: bool | None = None


# ── Admin — Products ───────────────────────────────────────────────

class AdminProductListItem(BaseModel):
    product_id: int
    code: str
    name: str
    category_id: int
    category_name: str
    unit: str
    base_price: float
    is_active: bool

    model_config = {"from_attributes": True}


class AdminProductDetail(BaseModel):
    product_id: int
    code: str
    name: str
    category_id: int
    category_name: str
    is_fuel: bool
    unit: str
    base_price: float
    subsidy_per_unit: float | None = None
    tax_type_id: int | None = None
    tax_type_name: str | None = None
    tax_rate: float | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CreateProductRequest(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=2, max_length=150)
    category_id: int
    unit: str = "UNIDAD"
    base_price: float = Field(default=0, ge=0)
    subsidy_per_unit: float | None = Field(default=None, ge=0)
    tax_type_id: int | None = None
    is_active: bool = True


class UpdateProductRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    category_id: int | None = None
    unit: str | None = None
    base_price: float | None = Field(default=None, ge=0)
    subsidy_per_unit: float | None = None
    tax_type_id: int | None = None
    is_active: bool | None = None


# ── Admin — Grades ─────────────────────────────────────────────────

class AdminGradeListItem(BaseModel):
    grade_id: int
    code: str
    name: str
    product_id: int
    product_name: str
    product_code: str
    is_active: bool

    model_config = {"from_attributes": True}


class AdminGradeDetail(BaseModel):
    grade_id: int
    code: str
    name: str
    product_id: int
    product_name: str
    product_code: str
    product_unit: str
    is_active: bool

    model_config = {"from_attributes": True}


class CreateGradeRequest(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=2, max_length=100)
    product_id: int
    is_active: bool = True


class UpdateGradeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    product_id: int | None = None
    is_active: bool | None = None


# ── Admin — Price Lists ─────────────────────────────────────────────

class AdminPriceListItemDetail(BaseModel):
    price_list_item_id: int
    product_id: int
    product_name: str
    product_code: str
    unit_price: float
    is_active: bool

    model_config = {"from_attributes": True}


class AdminPriceListListItem(BaseModel):
    price_list_id: int
    code: str
    name: str
    is_default: bool
    item_count: int
    is_active: bool

    model_config = {"from_attributes": True}


class AdminPriceListDetail(BaseModel):
    price_list_id: int
    code: str
    name: str
    is_default: bool
    is_active: bool
    items: list[AdminPriceListItemDetail] = []

    model_config = {"from_attributes": True}


class CreatePriceListRequest(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=2, max_length=100)
    is_default: bool = False


class UpdatePriceListRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    is_default: bool | None = None
    is_active: bool | None = None


class CreatePriceListItemRequest(BaseModel):
    product_id: int
    unit_price: float = Field(gt=0)


class UpdatePriceListItemRequest(BaseModel):
    unit_price: float | None = Field(default=None, gt=0)
    is_active: bool | None = None


# ── Admin — Dispensers ──────────────────────────────────────────────

class AdminDispenserHoseDetail(BaseModel):
    hose_id: int
    side: str
    fusion_pump_id: int
    fusion_hose_id: int
    grade_code: str
    grade_name: str
    is_active: bool

    model_config = {"from_attributes": True}


class AdminDispenserListItem(BaseModel):
    dispenser_id: int
    code: str
    name: str
    emission_point_label: str | None = None
    printer_ip: str | None = None
    printer_port: int = 9100
    hose_count: int = 0
    sort_order: int = 0
    is_active: bool

    model_config = {"from_attributes": True}


class AdminDispenserDetail(BaseModel):
    dispenser_id: int
    code: str
    name: str
    emission_point_id: int | None = None
    emission_point_label: str | None = None
    printer_ip: str | None = None
    printer_port: int = 9100
    sort_order: int = 0
    is_active: bool
    hoses: list[AdminDispenserHoseDetail] = []

    model_config = {"from_attributes": True}


class CreateDispenserRequest(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(min_length=2, max_length=100)
    emission_point_id: int | None = None
    printer_ip: str | None = None
    printer_port: int = 9100
    sort_order: int = 0


class UpdateDispenserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    emission_point_id: int | None = None
    printer_ip: str | None = None
    printer_port: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class CreateHoseRequest(BaseModel):
    side: str = Field(min_length=1, max_length=1, pattern=r"^[AB]$")
    fusion_pump_id: int
    fusion_hose_id: int
    grade_code: str = Field(min_length=2, max_length=20)


class UpdateHoseRequest(BaseModel):
    grade_code: str | None = Field(default=None, min_length=2, max_length=20)
    fusion_pump_id: int | None = None
    fusion_hose_id: int | None = None
    is_active: bool | None = None


# ── Admin — Emission Points ────────────────────────────────────────

class AdminEmissionPointListItem(BaseModel):
    emission_point_id: int
    establishment: str
    emission_point: str
    label: str  # e.g., "001-001"
    doc_type: str
    current_sequential: int
    is_active: bool

    model_config = {"from_attributes": True}


class AdminEmissionPointDetail(BaseModel):
    emission_point_id: int
    establishment: str
    emission_point: str
    label: str
    doc_type: str
    current_sequential: int
    sequential_start: int
    sequential_end: int
    authorization_number: str | None = None
    authorization_date: date | None = None
    authorization_expiry: date | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class CreateEmissionPointRequest(BaseModel):
    establishment: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]+$")
    emission_point: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]+$")
    doc_type: str = "FACTURA"
    sequential_start: int = Field(ge=1)
    sequential_end: int = Field(ge=1)
    authorization_number: str | None = None
    authorization_date: date | None = None
    authorization_expiry: date | None = None


class UpdateEmissionPointRequest(BaseModel):
    doc_type: str | None = None
    current_sequential: int | None = Field(default=None, ge=1)
    sequential_start: int | None = Field(default=None, ge=1)
    sequential_end: int | None = Field(default=None, ge=1)
    authorization_number: str | None = None
    authorization_date: date | None = None
    authorization_expiry: date | None = None
    is_active: bool | None = None


# ── Admin — Company Info ────────────────────────────────────────────

class AdminCompanyInfoResponse(BaseModel):
    company_id: int
    ruc: str
    name: str
    commercial_name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    province: str | None = None
    country: str | None = None
    fiscal_regime: str | None = None
    sri_environment: int | None = None
    emission_type: int | None = None
    logo_url: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class UpdateCompanyInfoRequest(BaseModel):
    ruc: str | None = None
    name: str | None = None
    commercial_name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    province: str | None = None
    country: str | None = None
    fiscal_regime: str | None = None
    sri_environment: int | None = None
    emission_type: int | None = None
    logo_url: str | None = None
    is_active: bool | None = None


# ── Admin — System Config ───────────────────────────────────────────

class AdminSystemConfigItem(BaseModel):
    key: str
    value: str
    description: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UpdateSystemConfigRequest(BaseModel):
    value: str
    description: str | None = None


# ── Admin — Payment Methods ─────────────────────────────────────────

class AdminPaymentMethodListItem(BaseModel):
    payment_method_id: int
    code: str
    name: str
    sri_code: str
    requires_reference: bool
    is_active: bool

    model_config = {"from_attributes": True}


class AdminPaymentMethodDetail(BaseModel):
    payment_method_id: int
    code: str
    name: str
    sri_code: str
    requires_reference: bool
    is_active: bool

    model_config = {"from_attributes": True}


class CreatePaymentMethodRequest(BaseModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Z0-9_]+$")
    name: str = Field(min_length=2, max_length=100)
    sri_code: str = Field(min_length=2, max_length=3, default="20")
    requires_reference: bool = False
    is_active: bool = True


class UpdatePaymentMethodRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    sri_code: str | None = Field(default=None, min_length=2, max_length=3)
    requires_reference: bool | None = None
    is_active: bool | None = None


# ── Admin — Dashboard ──────────────────────────────────────────────

class DashboardSummary(BaseModel):
    total_sales: float = 0
    total_gallons: float = 0
    dispatch_count: int = 0
    avg_ticket: float = 0
    cash_collected: float = 0
    non_cash_collected: float = 0
    active_shifts: int = 0
    date_from: date
    date_to: date


class SalesByDayItem(BaseModel):
    date: date | str  # date for daily/monthly, str like "2026-06-26T14:00" for hourly
    total: float
    total_gallons: float = 0
    count: int


class SalesByProductItem(BaseModel):
    product_name: str
    product_code: str
    total_amount: float
    total_liters: float = 0
    count: int


class SalesByPaymentItem(BaseModel):
    method_name: str
    method_code: str
    total: float
    count: int


class TopCustomerItem(BaseModel):
    person_id: int | None = None
    customer_name: str
    id_number: str | None = None
    total: float
    count: int


class TopProductItem(BaseModel):
    product_name: str
    product_code: str
    total_amount: float
    total_liters: float = 0
    count: int


class EvolutionItem(BaseModel):
    """One bucket in a time-series chart (hour / day / month)."""
    period_label: str  # "2026-06-26T14:00" or "2026-06-01" or "2026-01"
    sales: float = 0
    gallons: float = 0
    count: int = 0


class CompareResponse(BaseModel):
    """Current vs previous period KPI comparison."""
    current: DashboardSummary
    previous: DashboardSummary
    growth_sales_pct: float | None = None  # null if previous was 0
    growth_gallons_pct: float | None = None


class EvolutionCompareResponse(BaseModel):
    """Three-period evolution data for comparison charts."""
    period: str  # "daily", "monthly", "annual"
    current_label: str
    previous_label: str
    next_label: str
    previous: list[EvolutionItem]
    current: list[EvolutionItem]
    next: list[EvolutionItem]


class TopPeriodItem(BaseModel):
    """Best sub-periods within a larger period (best days in month, best months in year)."""
    period_label: str  # "26 Jun" or "Junio"
    sales: float
    gallons: float
    count: int


class GallonsByPeriodItem(BaseModel):
    """Gallons volume in a time bucket, broken down by product."""
    period_label: str  # "2026-06-26T08:00" or "2026-06-15" or "2026-06"
    product_id: int
    product_name: str
    product_code: str
    gallons: float
    count: int


# ── Admin — Reports ─────────────────────────────────────────────────

class ReportSalesItem(BaseModel):
    order_id: str
    date: str | None = None
    dispenser_name: str | None = None
    grade: str | None = None
    customer_name: str | None = None
    id_number: str | None = None
    plate: str | None = None
    payment_method: str | None = None
    amount: float = 0
    volume: float | None = None
    status: str
    sri_status: str | None = None
    access_key: str | None = None
    authorized_by: str | None = None
    shift_id: int | None = None
    contract_code: str | None = None


class ReportDispatchItem(BaseModel):
    order_id: str
    date: str | None = None
    shift_id: int
    dispenser_name: str | None = None
    hose_side: str | None = None
    grade: str | None = None
    customer_name: str | None = None
    id_number: str | None = None
    plate: str | None = None
    payment_method: str | None = None
    amount: float = 0
    volume: float | None = None
    unit_price: float | None = None
    tax_amount: float | None = None
    status: str
    sri_status: str | None = None
    access_key: str | None = None
    credit_status: str | None = None
    authorized_by: str | None = None


class ReportShiftItem(BaseModel):
    shift_id: int
    user_name: str
    opened_at: str | None = None
    closed_at: str | None = None
    status: str
    opening_cash: float = 0
    collected: float = 0
    collected_cash: float = 0
    efectivo_actual: float = 0
    surplus: float = 0
    shortage: float = 0
    dispatch_count: int = 0


class ReportCashSummaryItem(BaseModel):
    shift_id: int
    user_name: str
    type: str
    amount: float = 0
    observation: str | None = None
    date: str | None = None
    running_balance: float = 0


# ── Bulk Invoice / Liquidación Sector Público ──────────────

class BulkInvoiceRequest(BaseModel):
    contract_id: int
    emission_point_id: int


class BulkInvoiceResponse(BaseModel):
    invoice_id: str | None = None
    access_key: str | None = None
    sri_status: str | None = None
    dispatch_count: int = 0
    total_amount: float = 0.0
    invoiced_dispatch_ids: list[int] = []
    errors: list[str] = []


class PendingBulkDispatchItem(BaseModel):
    dispatch_id: int
    order_id: str
    dispatch_date: str | None = None
    plate: str | None = None
    product_code: str = ""
    product_name: str = ""
    quantity: float = 0
    unit_price: float = 0
    subtotal: float = 0
    tax_amount: float = 0
    total: float = 0
