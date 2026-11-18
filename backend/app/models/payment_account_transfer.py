from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentAccountTransfer(Base):
    __tablename__ = "payment_account_transfers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "source_account_id"],
            ["payment_accounts.tenant_id", "payment_accounts.id"],
            name="fk_payment_transfers_source_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "target_account_id"],
            ["payment_accounts.tenant_id", "payment_accounts.id"],
            name="fk_payment_transfers_target_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_payment_account_transfers_positive_amount",
        ),
        CheckConstraint(
            "source_account_id <> target_account_id",
            name="ck_payment_account_transfers_distinct_accounts",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    source_account_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    target_account_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    transfer_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
