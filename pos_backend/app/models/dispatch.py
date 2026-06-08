"""Dispatches, details, payments, cash movements, and transfers."""

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey,
    Integer, Numeric, String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class DispatchType(Base):
    __tablename__ = "dispatch_types"

    dispatch_type_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    requires_customer: Mapped[bool] = mapped_column(Boolean, default=True)
    affects_cash: Mapped[bool] = mapped_column(Boolean, default=True)


class Dispatch(Base):
    __tablename__ = "dispatches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AUTHORIZED', 'COMPLETED', 'COLLECTED', 'CANCELLED')",
            name="ck_dispatches_status",
        ),
        CheckConstraint(
            "credit_status IS NULL OR credit_status IN ('PENDING_INVOICE', 'INVOICED')",
            name="ck_dispatches_credit_status",
        ),
    )

    dispatch_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.shift_id"), nullable=False
    )
    dispenser_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispensers.dispenser_id"), nullable=False
    )
    emission_point_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("emission_points.emission_point_id")
    )
    sequential_number: Mapped[str | None] = mapped_column(String(20))
    dispatch_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispatch_types.dispatch_type_id"), nullable=False
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vehicles.vehicle_id")
    )
    person_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("persons.person_id")
    )
    credit_contract_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("credit_contracts.contract_id")
    )
    credit_status: Mapped[str | None] = mapped_column(String(20))
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(15), default="AUTHORIZED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authorized_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.user_id")
    )
    hose_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hoses.hose_id")
    )
    grade_id: Mapped[str | None] = mapped_column(String(20))
    access_key: Mapped[str | None] = mapped_column(
        String(49), comment="SRI access key (49 digits, computed at invoicing)"
    )


class DispatchDetail(Base):
    __tablename__ = "dispatch_details"

    detail_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispatch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispatches.dispatch_id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.product_id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    price_without_subsidy: Mapped[float | None] = mapped_column(
        Numeric(10, 4), comment="unit_price + subsidy_per_unit at time of sale"
    )
    subsidy_amount: Mapped[float | None] = mapped_column(
        Numeric(12, 2), comment="quantity × subsidy_per_unit at time of sale"
    )
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)


class DispatchPayment(Base):
    __tablename__ = "dispatch_payments"

    payment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispatch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispatches.dispatch_id"), nullable=False
    )
    payment_method_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payment_methods.payment_method_id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reference_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CashMovement(Base):
    __tablename__ = "cash_movements"
    __table_args__ = (
        CheckConstraint(
            "type IN ('INCOME', 'EXPENSE', 'SAFE_DROP', 'TRANSFER_OUT')",
            name="ck_cash_movements_type",
        ),
    )

    movement_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.shift_id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    observation: Mapped[str | None] = mapped_column(String(300))
    running_balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    related_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.user_id")
    )
    related_user_name: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transfer(Base):
    __tablename__ = "transfers"

    transfer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.shift_id"), nullable=False
    )
    to_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.user_id"))
    to_user_name: Mapped[str] = mapped_column(String(150), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    observation: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
