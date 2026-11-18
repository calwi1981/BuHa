from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey,
    Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ManualBooking(Base):
    __tablename__ = "manual_bookings"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "booking_number",
            name="uq_manual_bookings_tenant_number",
        ),
        CheckConstraint(
            "booking_type IN ('income', 'expense')",
            name="ck_manual_bookings_type",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_manual_bookings_positive_amount",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    booking_number: Mapped[str] = mapped_column(
        String(100), nullable=False,
    )
    booking_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )
    booking_date: Mapped[date] = mapped_column(
        Date, nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False,
    )
    payment_account_id: Mapped[int] = mapped_column(
        ForeignKey("payment_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
