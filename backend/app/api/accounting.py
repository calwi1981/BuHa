from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.account import Account
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.payment import Payment
from app.services.accounting import allocate_payment, money

router = APIRouter(prefix="/api/accounting", tags=["Buchhaltung"])


def get_payment_rows(db, start, end):
    payments = db.scalars(
        select(Payment)
        .where(Payment.payment_date >= start)
        .where(Payment.payment_date < end)
        .order_by(Payment.payment_date, Payment.id)
    ).all()

    rows = []

    for payment in payments:
        invoice = db.get(Invoice, payment.invoice_id)

        if invoice is None:
            raise HTTPException(500, "Zahlung ohne Rechnung.")

        lines = db.scalars(
            select(InvoiceLine)
            .where(InvoiceLine.invoice_id == invoice.id)
            .order_by(InvoiceLine.position)
        ).all()

        try:
            previous_payments = db.scalars(
                select(Payment)
                .where(Payment.invoice_id == invoice.id)
                .where(
                    (Payment.payment_date < payment.payment_date)
                    | (
                        (Payment.payment_date == payment.payment_date)
                        & (Payment.id < payment.id)
                    )
                )
            ).all()

            previously_paid = sum(
                (item.amount for item in previous_payments),
                Decimal("0"),
            )

            allocations = allocate_payment(
                payment.amount,
                invoice.gross_total,
                lines,
                previously_paid=previously_paid,
            )
        except ValueError as exc:
            raise HTTPException(500, str(exc))

        for allocation in allocations:
            account = (
                db.get(Account, allocation["account_id"])
                if allocation["account_id"] is not None
                else None
            )

            rows.append({
                "payment_id": payment.id,
                "payment_date": payment.payment_date,
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "invoice_type": invoice.invoice_type,
                "partner_id": invoice.partner_id,
                "description": allocation["description"],
                "account_id": allocation["account_id"],
                "account_number": account.number if account else None,
                "account_name": account.name if account else None,
                "vat_rate": allocation["vat_rate"],
                "net": allocation["net"],
                "vat": allocation["vat"],
                "gross": allocation["gross"],
            })

    return rows


@router.get("/journal")
def monthly_journal(
    db: DatabaseSession,
    user: CurrentUser,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
):
    start = date(year, month, 1)

    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    rows = get_payment_rows(db, start, end)


    from datetime import timedelta
    from decimal import Decimal
    from sqlalchemy import select
    from app.models.payment import Payment
    from app.models.invoice import Invoice
    from app.api.administration import load_settings

    settings = load_settings(db)
    opening_date_raw = settings.get("bank_opening_date", "")
    opening_balance_raw = settings.get("bank_opening_balance", "0.00")

    bank_opening_balance = None
    bank_closing_balance = None
    bank_incoming = Decimal("0")
    bank_outgoing = Decimal("0")

    if opening_date_raw:
        opening_date = date.fromisoformat(opening_date_raw)
        opening_balance = Decimal(str(opening_balance_raw))

        month_start = date(year, month, 1)

        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        month_end = next_month - timedelta(days=1)

        if opening_date == month_start:
            bank_opening_balance = opening_balance
        elif opening_date < month_start:
            bank_opening_balance = calculate_bank_balance(
                db,
                opening_date,
                opening_balance,
                month_start - timedelta(days=1),
            )

        if opening_date <= month_end:
            bank_closing_balance = calculate_bank_balance(
                db,
                opening_date,
                opening_balance,
                month_end,
            )

            payments = db.execute(
                select(Payment.amount, Invoice.invoice_type)
                .join(Invoice, Payment.invoice_id == Invoice.id)
                .where(Payment.payment_date >= month_start)
                .where(Payment.payment_date < next_month)
                .where(Payment.payment_date >= opening_date)
                .where(func.lower(func.trim(Payment.payment_method)) == "bank")
            ).all()

            for amount, invoice_type in payments:
                if invoice_type == "outgoing":
                    bank_incoming += amount
                elif invoice_type == "incoming":
                    bank_outgoing += amount

    return {
        "bank_opening_balance": bank_opening_balance,
        "bank_incoming": bank_incoming,
        "bank_outgoing": bank_outgoing,
        "bank_closing_balance": bank_closing_balance,
        "bank_opening_date": opening_date_raw,

        "year": year,
        "month": month,
        "rows": rows,
        "net_total": money(sum((r["net"] for r in rows), Decimal("0"))),
        "vat_total": money(sum((r["vat"] for r in rows), Decimal("0"))),
        "gross_total": money(sum((r["gross"] for r in rows), Decimal("0"))),
    }


@router.get("/eur")
def annual_eur(
    db: DatabaseSession,
    user: CurrentUser,
    year: int = Query(ge=2000, le=2099),
):
    from sqlalchemy import select

    rows = get_payment_rows(
        db,
        date(year, 1, 1),
        date(year + 1, 1, 1),
    )

    grouped = defaultdict(
        lambda: {
            "net": Decimal("0"),
            "vat": Decimal("0"),
            "gross": Decimal("0"),
        }
    )

    for row in rows:
        key = (
            row["invoice_type"],
            row["account_number"],
            row["account_name"],
        )

        grouped[key]["net"] += row["net"]
        grouped[key]["vat"] += row["vat"]
        grouped[key]["gross"] += row["gross"]

    accounts = []

    for key, totals in sorted(grouped.items(), key=lambda item: str(item[0])):
        invoice_type, account_number, account_name = key

        accounts.append({
            "invoice_type": invoice_type,
            "account_number": account_number,
            "account_name": account_name,
            "net": money(totals["net"]),
            "vat": money(totals["vat"]),
            "gross": money(totals["gross"]),
        })

    income = money(sum(
        (r["net"] for r in rows if r["invoice_type"] == "outgoing"),
        Decimal("0"),
    ))

    expenses = money(sum(
        (r["net"] for r in rows if r["invoice_type"] == "incoming"),
        Decimal("0"),
    ))


    output_vat_total = Decimal("0.00")
    input_vat_total = Decimal("0.00")

    for account_row in accounts:
        vat = Decimal(str(account_row.get("vat", 0) or 0))
        account_type = account_row.get("invoice_type")

        if account_type == "outgoing":
            output_vat_total += vat
        elif account_type == "incoming":
            account_number = account_row.get("account_number")
            account = db.execute(
                select(Account)
                .where(Account.number == str(account_number))
            ).scalar_one_or_none() if account_number is not None else None

            if account and account.tax_treatment == "input_vat":
                deductible = Decimal(
                    str(account.input_vat_deductible_percent)
                )
                input_vat_total += (
                    vat * deductible / Decimal("100")
                )

    output_vat_total = output_vat_total.quantize(Decimal("0.01"))
    input_vat_total = input_vat_total.quantize(Decimal("0.01"))
    vat_difference = output_vat_total - input_vat_total

    return {
        "output_vat_total": output_vat_total,
        "input_vat_total": input_vat_total,
        "vat_difference": vat_difference,

        "year": year,
        "income_net": income,
        "expenses_net": expenses,
        "result_net": money(income - expenses),
        "accounts": accounts,
    }


def calculate_bank_balance(db, opening_date, opening_balance, target_date):
    """Berechnet den Bankbestand bis einschliesslich target_date."""
    from decimal import Decimal
    from sqlalchemy import select
    from app.models.payment import Payment
    from app.models.invoice import Invoice

    balance = Decimal(str(opening_balance))

    if target_date < opening_date:
        return None

    payments = db.execute(
        select(Payment.amount, Invoice.invoice_type)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Payment.payment_date >= opening_date)
        .where(Payment.payment_date <= target_date)
        .where(func.lower(func.trim(Payment.payment_method)) == "bank")
    ).all()

    for amount, invoice_type in payments:
        if invoice_type == "outgoing":
            balance += amount
        elif invoice_type == "incoming":
            balance -= amount

    return balance
