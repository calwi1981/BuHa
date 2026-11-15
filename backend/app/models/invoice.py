from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False)
    supplier_reference: Mapped[str | None] = mapped_column(String(100))

    partner_id: Mapped[int] = mapped_column(
        ForeignKey("partners.id", ondelete="RESTRICT"), nullable=False
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    net_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    vat_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    gross_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    xrechnung_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    xrechnung_buyer_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
