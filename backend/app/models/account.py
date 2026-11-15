from decimal import Decimal
from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    default_vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=0, nullable=False
    )
    tax_treatment: Mapped[str] = mapped_column(
        String(30), default="none", nullable=False
    )
    input_vat_deductible_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=100, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
