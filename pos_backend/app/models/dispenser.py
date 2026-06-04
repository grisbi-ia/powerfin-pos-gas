"""Dispensers and hoses — physical layout mapping to Fusion pump IDs."""

from sqlalchemy import Boolean, CHAR, ForeignKey, Integer, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Dispenser(Base):
    __tablename__ = "dispensers"

    dispenser_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emission_point_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("emission_points.emission_point_id")
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    fusion_pump_id: Mapped[int] = mapped_column(Integer, nullable=False)
    printer_ip: Mapped[str | None] = mapped_column(String(45))
    printer_port: Mapped[int] = mapped_column(Integer, default=9100)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    hoses: Mapped[list["Hose"]] = relationship(back_populates="dispenser")


class Hose(Base):
    __tablename__ = "hoses"
    __table_args__ = (
        CheckConstraint("side IN ('A', 'B')", name="ck_hoses_side"),
    )

    hose_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispenser_id: Mapped[int] = mapped_column(Integer, ForeignKey("dispensers.dispenser_id"), nullable=False)
    side: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    fusion_pump_id: Mapped[int] = mapped_column(Integer, nullable=False)
    fusion_hose_id: Mapped[int] = mapped_column(Integer, nullable=False)
    grade_id: Mapped[str] = mapped_column(String(20), nullable=False)

    dispenser: Mapped["Dispenser"] = relationship(back_populates="hoses")
