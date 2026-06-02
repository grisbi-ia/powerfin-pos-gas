"""Company info (single row) and system configuration (key-value)."""

from sqlalchemy import Boolean, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CompanyInfo(Base):
    __tablename__ = "company_info"

    company_id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    ruc: Mapped[str] = mapped_column(String(13), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    commercial_name: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(100))
    logo_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
