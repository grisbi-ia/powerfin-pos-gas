"""Payment methods."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    payment_method_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    requires_reference: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
