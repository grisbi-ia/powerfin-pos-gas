"""Products, categories, tax types, and fuel grades."""

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductCategory(Base):
    __tablename__ = "product_categories"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_fuel: Mapped[bool] = mapped_column(Boolean, default=False)


class TaxType(Base):
    __tablename__ = "tax_types"

    tax_type_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0)


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_categories.category_id"), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(20), default="UNIDAD")
    base_price: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    tax_type_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tax_types.tax_type_id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Grade(Base):
    __tablename__ = "grades"

    grade_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.product_id"), nullable=False
    )
