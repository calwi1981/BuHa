from decimal import Decimal
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), default="Stueck", nullable=False)
    unit_net_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    discount_type: Mapped[str] = mapped_column(
        String(10), default="none", nullable=False
    )
    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )

    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT")
    )
    net_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    gross_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
