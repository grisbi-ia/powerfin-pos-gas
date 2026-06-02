"""Shifts — user work sessions with cash tracking."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey,
    Integer, Numeric, String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_shifts_status"),
    )

    shift_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.user_id"), nullable=False
    )
    opening_cash: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    closing_cash: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accounting_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
