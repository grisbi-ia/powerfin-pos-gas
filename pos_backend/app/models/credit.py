"""Credit contracts — fleet, product amounts, contract types."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class CreditContract(Base):
    __tablename__ = "credit_contracts"
    __table_args__ = (
        CheckConstraint(
            "contract_type IN ('INDEFINIDO', 'NO_INDEFINIDO')",
            name="ck_credit_contracts_type",
        ),
        CheckConstraint(
            "sercop_type IN ('INFIMA_CUANTIA', 'ADJUDICACION', 'CONTRATACION_DIRECTA', 'NO_DEFINIDO')",
            name="ck_credit_contracts_sercop",
        ),
    )

    contract_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("persons.person_id"), nullable=False
    )
    contract_date: Mapped[date] = mapped_column(Date, default=func.current_date())
    cupo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(15), nullable=False)
    sercop_type: Mapped[str] = mapped_column(String(30), default="NO_DEFINIDO")
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vehicles: Mapped[list["CreditContractVehicle"]] = relationship(
        back_populates="contract", lazy="selectin"
    )
    products: Mapped[list["CreditContractProduct"]] = relationship(
        back_populates="contract", lazy="selectin"
    )


class CreditContractVehicle(Base):
    __tablename__ = "credit_contract_vehicles"
    __table_args__ = (
        UniqueConstraint("contract_id", "vehicle_id", name="uq_contract_vehicle"),
    )

    contract_vehicle_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("credit_contracts.contract_id"), nullable=False
    )
    vehicle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicles.vehicle_id"), nullable=False
    )
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    contract: Mapped["CreditContract"] = relationship(back_populates="vehicles")


class CreditContractProduct(Base):
    __tablename__ = "credit_contract_products"
    __table_args__ = (
        UniqueConstraint("contract_id", "product_id", name="uq_contract_product"),
    )

    contract_product_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    contract_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("credit_contracts.contract_id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.product_id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    contract: Mapped["CreditContract"] = relationship(back_populates="products")
