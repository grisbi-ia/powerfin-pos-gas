"""Persons (customers) and vehicles."""

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Person(Base):
    __tablename__ = "persons"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_type: Mapped[str] = mapped_column(String(5), nullable=False)
    id_number: Mapped[str] = mapped_column(String(13), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(100))
    price_list_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("price_lists.price_list_id")
    )
    yalobox_wallet: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("id_type", "id_number", name="persons_id_type_id_number_key"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plate: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("persons.person_id"), nullable=False
    )
    price_list_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("price_lists.price_list_id")
    )
    billing_person_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("persons.person_id"), nullable=True,
        comment="Preferred billing person. NULL = use owner (person_id)."
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_container_sale: Mapped[bool] = mapped_column(Boolean, default=False, comment="Allow this vehicle to be used when customer has no vehicle")

    person: Mapped["Person"] = relationship(lazy="selectin", foreign_keys=[person_id])
    billing_person: Mapped["Person | None"] = relationship(lazy="selectin", foreign_keys=[billing_person_id])
