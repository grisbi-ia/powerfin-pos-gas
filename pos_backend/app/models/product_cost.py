"""Purchase cost history per product (effective-dated).

Each row means: from ``valid_from`` onward, this is the purchase cost per unit.
The "valid to" date is not stored; it is derived from the next row's
``valid_from`` (see ``app.services.cost_service``). This makes gaps and
overlaps impossible by construction.

`cost_price` is NET of VAT (the accounting-correct value for gross margin).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductCost(Base):
    __tablename__ = "product_cost_history"
    __table_args__ = (
        UniqueConstraint("product_id", "valid_from", name="uq_product_cost_valid_from"),
    )

    product_cost_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.product_id"), nullable=False, index=True
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    cost_price: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="MANUAL", nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.user_id")
    )
