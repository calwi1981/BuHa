from datetime import date as utility_date
from decimal import Decimal as UtilityDecimal
from sqlalchemy import Date as UtilityDate, Numeric as UtilityNumeric
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import UniqueConstraint, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_number", name="uq_invoices_tenant_invoice_number"),)

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
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
    utility_period_from: Mapped[utility_date | None] = mapped_column(UtilityDate, nullable=True)
    utility_period_to: Mapped[utility_date | None] = mapped_column(UtilityDate, nullable=True)
    utility_prepayments: Mapped[UtilityDecimal | None] = mapped_column(UtilityNumeric(12, 2), nullable=True)
    utility_total_cost: Mapped[UtilityDecimal | None] = mapped_column(UtilityNumeric(12, 2), nullable=True)
    utility_difference: Mapped[UtilityDecimal | None] = mapped_column(UtilityNumeric(12, 2), nullable=True)
    utility_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
