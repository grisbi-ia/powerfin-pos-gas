"""SRI emission points — atomic sequential number consumption."""

from sqlalchemy import BigInteger, Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EmissionPoint(Base):
    __tablename__ = "emission_points"

    emission_point_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    establishment: Mapped[str] = mapped_column(String(3), nullable=False)
    emission_point: Mapped[str] = mapped_column(String(3), nullable=False)
    current_sequential: Mapped[int] = mapped_column(BigInteger, default=1)
    sequential_start: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sequential_end: Mapped[int] = mapped_column(BigInteger, nullable=False)
    doc_type: Mapped[str] = mapped_column(String(20), default="FACTURA")
    authorization_number: Mapped[str | None] = mapped_column(String(50))
    authorization_date: Mapped[Date | None] = mapped_column(Date)
    authorization_expiry: Mapped[Date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
