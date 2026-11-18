from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.manual_booking import ManualBooking
from app.models.payment import Payment
from app.models.payment_account import PaymentAccount
from app.models.payment_account_transfer import PaymentAccountTransfer


def calculate_payment_account_balance(
    db: Session,
    tenant_id: int,
    account_id: int,
    target_date: date,
) -> Decimal | None:
    """Kontostand eines Zahlungskontos zum angegebenen Datum."""

    account = db.scalar(
        select(PaymentAccount).where(
            PaymentAccount.id == account_id,
            PaymentAccount.tenant_id == tenant_id,
        )
    )

    if account is None:
        return None

    if target_date < account.opening_date:
        return None

    balance = Decimal(str(account.opening_balance))

    payments = db.execute(
        select(Payment.amount, Invoice.invoice_type)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.tenant_id == tenant_id)
        .where(Payment.payment_account_id == account.id)
        .where(Payment.payment_date >= account.opening_date)
        .where(Payment.payment_date <= target_date)
        .order_by(Payment.payment_date, Payment.id)
    ).all()

    for amount, invoice_type in payments:
        if invoice_type == "outgoing":
            balance += amount
        elif invoice_type == "incoming":
            balance -= amount

    # Direkte Einnahmen und Ausgaben ohne Rechnung
    manual_bookings = db.execute(
        select(
            ManualBooking.amount,
            ManualBooking.booking_type,
        )
        .where(
            ManualBooking.tenant_id == tenant_id,
            ManualBooking.payment_account_id == account.id,
            ManualBooking.booking_date >= account.opening_date,
            ManualBooking.booking_date <= target_date,
        )
        .order_by(
            ManualBooking.booking_date,
            ManualBooking.id,
        )
    ).all()

    for amount, booking_type in manual_bookings:
        if booking_type == "income":
            balance += amount
        elif booking_type == "expense":
            balance -= amount

    outgoing_transfers = db.scalars(
        select(PaymentAccountTransfer.amount)
        .where(
            PaymentAccountTransfer.tenant_id == tenant_id,
            PaymentAccountTransfer.source_account_id == account.id,
            PaymentAccountTransfer.transfer_date >= account.opening_date,
            PaymentAccountTransfer.transfer_date <= target_date,
        )
    ).all()

    incoming_transfers = db.scalars(
        select(PaymentAccountTransfer.amount)
        .where(
            PaymentAccountTransfer.tenant_id == tenant_id,
            PaymentAccountTransfer.target_account_id == account.id,
            PaymentAccountTransfer.transfer_date >= account.opening_date,
            PaymentAccountTransfer.transfer_date <= target_date,
        )
    ).all()

    balance -= sum(outgoing_transfers, Decimal("0"))
    balance += sum(incoming_transfers, Decimal("0"))

    return balance.quantize(Decimal("0.01"))


def list_payment_account_balances(
    db: Session,
    tenant_id: int,
    target_date: date,
) -> list[dict]:
    """Kontostaende aller Zahlungskonten eines Mandanten."""

    accounts = db.scalars(
        select(PaymentAccount)
        .where(PaymentAccount.tenant_id == tenant_id)
        .order_by(PaymentAccount.name, PaymentAccount.id)
    ).all()

    result = []

    for account in accounts:
        balance = calculate_payment_account_balance(
            db,
            tenant_id,
            account.id,
            target_date,
        )

        result.append({
            "id": account.id,
            "name": account.name,
            "opening_balance": account.opening_balance,
            "opening_date": account.opening_date,
            "is_active": account.is_active,
            "balance": balance,
            "balance_date": target_date,
        })

    return result
