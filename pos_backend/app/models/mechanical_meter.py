"""Mechanical flow meters — physical counters on dispensers.

Each meter belongs to a dispenser and is mapped either:
- PRODUCT type: one meter per product/grade across all hoses of that product
- HOSE type: one meter per physical hose
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class MechanicalMeter(Base):
    __tablename__ = "mechanical_meters"
    __table_args__ = (
        CheckConstraint(
            "(meter_type = 'PRODUCT' AND grade_id IS NOT NULL AND hose_id IS NULL) OR "
            "(meter_type = 'HOSE' AND hose_id IS NOT NULL AND grade_id IS NULL)",
            name="ck_meter_mapping",
        ),
        CheckConstraint(
            "meter_type IN ('PRODUCT', 'HOSE')",
            name="ck_meter_type",
        ),
    )

    meter_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispenser_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispensers.dispenser_id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    meter_type: Mapped[str] = mapped_column(String(20), nullable=False)
    grade_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("grades.grade_id"), nullable=True
    )
    hose_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hoses.hose_id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    dispenser: Mapped["Dispenser"] = relationship(back_populates="mechanical_meters")
    grade: Mapped["Grade | None"] = relationship()
    hose: Mapped["Hose | None"] = relationship()
    readings: Mapped[list["MeterReading"]] = relationship(back_populates="meter")


class MeterReading(Base):
    __tablename__ = "meter_readings"
    __table_args__ = (
        CheckConstraint(
            "reading_type IN ('OPENING', 'CLOSING')",
            name="ck_reading_type",
        ),
        UniqueConstraint("meter_id", "shift_id", "reading_type",
                         name="uq_reading_meter_shift_type"),
    )

    reading_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    meter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mechanical_meters.meter_id"), nullable=False
    )
    shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.shift_id"), nullable=False
    )
    reading_type: Mapped[str] = mapped_column(String(10), nullable=False)
    reading_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recorded_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.user_id"), nullable=False
    )

    # Relationships
    meter: Mapped["MechanicalMeter"] = relationship(back_populates="readings")
    shift: Mapped["Shift"] = relationship()
    user: Mapped["User"] = relationship()
