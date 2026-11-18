from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func

from app.api.dependencies import TenantUser, DatabaseSession
from app.models.account import Account
from app.models.invoice import Invoice
from app.models.manual_booking import ManualBooking
from app.models.invoice_line import InvoiceLine
from app.models.payment import Payment
from app.models.payment_account import PaymentAccount
from app.services.accounting import allocate_payment, allocate_utility_payment, money

router = APIRouter(prefix="/api/accounting", tags=["Buchhaltung"])


def get_payment_rows(db, tenant_id, start, end):
    payment_account_names = {
        account.id: account.name
        for account in db.scalars(
            select(PaymentAccount).where(
                PaymentAccount.tenant_id == tenant_id
            )
        ).all()
    }

    payments = db.scalars(
        select(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.tenant_id == tenant_id)
        .where(Payment.payment_date >= start)
        .where(Payment.payment_date < end)
        .order_by(Payment.payment_date, Payment.id)
    ).all()

    rows = []

    for payment in payments:
        invoice = db.scalar(
            select(Invoice).where(
                Invoice.id == payment.invoice_id,
                Invoice.tenant_id == tenant_id,
            )
        )

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

            if invoice.utility_period_from is not None:
                if invoice.utility_account_id is None:
                    raise ValueError(
                        "NK-Buchungskonto fehlt bei Rechnung "
                        + str(invoice.id)
                    )
                allocations = [{
                    "description": "Nebenkosten-Differenz "
                        + str(invoice.invoice_number),
                    "account_id": invoice.utility_account_id,
                    "vat_rate": 0,
                    "net": money(payment.amount),
                    "vat": money(0),
                    "gross": money(payment.amount),
                }] if payment.amount != 0 else []
            else:
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
                db.scalar(
                    select(Account).where(
                        Account.id == allocation["account_id"],
                        Account.tenant_id == tenant_id,
                    )
                )
                if allocation["account_id"] is not None
                else None
            )

            rows.append({
                "payment_id": payment.id,
                "payment_account_name": payment_account_names.get(
                    payment.payment_account_id, ""
                ),
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

    # Direkte Geldbuchungen als eigenstaendige Buchungszeilen
    bookings = db.scalars(
        select(ManualBooking)
        .where(
            ManualBooking.tenant_id == tenant_id,
            ManualBooking.booking_date >= start,
            ManualBooking.booking_date < end,
        )
        .order_by(
            ManualBooking.booking_date,
            ManualBooking.id,
        )
    ).all()

    for booking in bookings:
        account = db.scalar(
            select(Account).where(
                Account.id == booking.account_id,
                Account.tenant_id == tenant_id,
            )
        )

        if account is None:
            raise HTTPException(
                500,
                "Buchungskonto fehlt bei manueller Buchung "
                + str(booking.id),
            )

        # Steuerberechnung fuer direkte Buchungen aus dem Buchungskonto.
        # Der gespeicherte Buchungsbetrag ist immer der Bruttobetrag.
        gross = money(booking.amount)
        vat_rate = Decimal(str(account.default_vat_rate or 0))
        tax_treatment = account.tax_treatment or "none"

        taxable = (
            (booking.booking_type == "income"
             and tax_treatment == "output_vat")
            or
            (booking.booking_type == "expense"
             and tax_treatment == "input_vat")
        )

        if taxable and vat_rate > 0:
            vat = money(
                gross * vat_rate / (Decimal("100") + vat_rate)
            )
            net = money(gross - vat)
        else:
            vat = money(0)
            net = gross

        rows.append({
            "source_type": "manual_booking",
            "manual_booking_id": booking.id,
            "payment_account_name": payment_account_names.get(
                booking.payment_account_id, ""
            ),
            "payment_id": -booking.id,
            "payment_date": booking.booking_date,
            "invoice_id": None,
            "invoice_number": booking.booking_number,
            "invoice_type": (
                "outgoing"
                if booking.booking_type == "income"
                else "incoming"
            ),
            "partner_id": None,
            "description": (
                "Direkte Einnahme"
                if booking.booking_type == "income"
                else "Direkte Ausgabe"
            ),
            "account_id": booking.account_id,
            "account_number": account.number,
            "account_name": account.name,
            "vat_rate": vat_rate if taxable else Decimal("0"),
            "net": net,
            "vat": vat,
            "gross": gross,
        })

    rows.sort(
        key=lambda row: (
            row["payment_date"],
            row["payment_id"],
            str(row["account_number"] or ""),
        )
    )

    return rows


@router.get("/journal")
def monthly_journal(
    db: DatabaseSession,
    user: TenantUser,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
):
    start = date(year, month, 1)

    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    rows = get_payment_rows(db, user.tenant_id, start, end)


    from datetime import timedelta
    from app.models.payment_account import PaymentAccount
    from app.services.payment_account_balances import (
        calculate_payment_account_balance,
        list_payment_account_balances,
    )

    month_start = date(year, month, 1)
    month_end = end - timedelta(days=1)
    previous_day = month_start - timedelta(days=1)

    payment_accounts = list_payment_account_balances(
        db, user.tenant_id, month_end
    )

    accounts = db.scalars(
        select(PaymentAccount)
        .where(PaymentAccount.tenant_id == user.tenant_id)
        .order_by(PaymentAccount.id)
    ).all()

    bank_opening_balance = Decimal("0.00")
    bank_closing_balance = Decimal("0.00")
    bank_incoming = Decimal("0.00")
    bank_outgoing = Decimal("0.00")
    bank_new_account_openings = Decimal("0.00")

    for account in accounts:
        if account.opening_date <= previous_day:
            opening = calculate_payment_account_balance(
                db, user.tenant_id, account.id, previous_day
            )
            bank_opening_balance += opening or Decimal("0.00")
        elif account.opening_date == month_start:
            bank_opening_balance += account.opening_balance
        elif month_start < account.opening_date <= month_end:
            bank_new_account_openings += account.opening_balance

        if account.opening_date <= month_end:
            closing = calculate_payment_account_balance(
                db, user.tenant_id, account.id, month_end
            )
            bank_closing_balance += closing or Decimal("0.00")

    movements = db.execute(
        select(Payment.amount, Invoice.invoice_type)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .join(
            PaymentAccount,
            Payment.payment_account_id == PaymentAccount.id,
        )
        .where(Invoice.tenant_id == user.tenant_id)
        .where(PaymentAccount.tenant_id == user.tenant_id)
        .where(Payment.payment_date >= month_start)
        .where(Payment.payment_date < end)
        .where(Payment.payment_date >= PaymentAccount.opening_date)
    ).all()

    for amount, invoice_type in movements:
        if invoice_type == "outgoing":
            if amount >= 0:
                bank_incoming += amount
            else:
                bank_outgoing -= amount
        elif invoice_type == "incoming":
            if amount >= 0:
                bank_outgoing += amount
            else:
                bank_incoming -= amount

    # Direkte Einnahmen und Ausgaben in der Saldenkontrolle
    manual_movements = db.execute(
        select(
            ManualBooking.amount,
            ManualBooking.booking_type,
        )
        .join(
            PaymentAccount,
            ManualBooking.payment_account_id == PaymentAccount.id,
        )
        .where(
            ManualBooking.tenant_id == user.tenant_id,
            PaymentAccount.tenant_id == user.tenant_id,
            ManualBooking.booking_date >= month_start,
            ManualBooking.booking_date < end,
            ManualBooking.booking_date >= PaymentAccount.opening_date,
        )
    ).all()

    for amount, booking_type in manual_movements:
        if booking_type == "income":
            bank_incoming += amount
        elif booking_type == "expense":
            bank_outgoing += amount

    bank_opening_date = min(
        (account.opening_date for account in accounts),
        default=None,
    )

    expected_closing_balance = (
        bank_opening_balance
        + bank_new_account_openings
        + bank_incoming
        - bank_outgoing
    )

    if (
        expected_closing_balance.quantize(Decimal("0.01"))
        != bank_closing_balance.quantize(Decimal("0.01"))
    ):
        raise HTTPException(
            status_code=500,
            detail="Kontensalden des Monatsjournals sind nicht konsistent.",
        )

    return {
        "bank_opening_balance": bank_opening_balance,
        "bank_incoming": bank_incoming,
        "bank_outgoing": bank_outgoing,
        "bank_new_account_openings": bank_new_account_openings,
        "bank_closing_balance": bank_closing_balance,
        "bank_opening_date": bank_opening_date.isoformat() if bank_opening_date else "",
        "payment_accounts": payment_accounts,

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
    user: TenantUser,
    year: int = Query(ge=2000, le=2099),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort_by: str = Query(default="date"),
    group_by: str = Query(default="account"),
):
    from sqlalchemy import select

    if sort_by not in {"date", "account", "type"}:
        raise HTTPException(422, "Ungueltige EÜR-Sortierung.")

    if group_by not in {"date", "account", "type"}:
        raise HTTPException(422, "Ungueltige EÜR-Gruppierung.")

    start = date_from or date(year, 1, 1)
    last_day = date_to or date(year, 12, 31)

    if start > last_day:
        raise HTTPException(
            422,
            "Das Von-Datum darf nicht nach dem Bis-Datum liegen.",
        )

    if start.year < 2000 or last_day.year > 2099:
        raise HTTPException(
            422,
            "Der Auswertungszeitraum muss zwischen 2000 und 2099 liegen.",
        )

    rows = get_payment_rows(
        db,
        user.tenant_id,
        start,
        last_day + timedelta(days=1),
    )

    if sort_by == "date":
        rows.sort(key=lambda r: (
            r["payment_date"],
            r["payment_id"],
            str(r["account_number"] or ""),
        ))
    elif sort_by == "account":
        rows.sort(key=lambda r: (
            str(r["account_number"] or ""),
            r["payment_date"],
            r["payment_id"],
        ))
    else:
        rows.sort(key=lambda r: (
            r["invoice_type"],
            r["payment_date"],
            r["payment_id"],
        ))

    detail_rows = rows

    if group_by == "date":
        group_key = lambda r: str(r["payment_date"])
    elif group_by == "type":
        group_key = lambda r: (
            "Einnahmen" if r["invoice_type"] == "outgoing"
            else "Ausgaben"
        )
    else:
        group_key = lambda r: (
            str(r["account_number"] or "") + " - " +
            str(r["account_name"] or "Ohne Konto")
        )

    detail_groups = {}

    for row in detail_rows:
        key = group_key(row)

        if key not in detail_groups:
            detail_groups[key] = {
                "group": key,
                "net": Decimal("0"),
                "vat": Decimal("0"),
                "gross": Decimal("0"),
                "rows": [],
            }

        detail_groups[key]["net"] += row["net"]
        detail_groups[key]["vat"] += row["vat"]
        detail_groups[key]["gross"] += row["gross"]
        detail_groups[key]["rows"].append(row)

    grouped_details = []

    # Bei Gruppierung nach Buchungskonto die Kontengruppen
    # unabhängig von der Buchungsreihenfolge sortieren.
    # Einnahmekonten E zuerst, danach Ausgabenkonten A.
    if group_by == "account":
        detail_group_items = sorted(
            detail_groups.values(),
            key=lambda item: (
                0 if item["group"].startswith("E") else 1,
                item["group"].split(" - ", 1)[0],
            ),
        )
    else:
        detail_group_items = detail_groups.values()

    for item in detail_group_items:
        grouped_details.append({
            "group": item["group"],
            "net": money(item["net"]),
            "vat": money(item["vat"]),
            "gross": money(item["gross"]),
            "rows": item["rows"],
        })

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
                .where(Account.tenant_id == user.tenant_id)
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
        "date_from": start,
        "date_to": last_day,
        "sort_by": sort_by,
        "group_by": group_by,
        "detail_rows": detail_rows,
        "detail_groups": grouped_details,
        "income_net": income,
        "expenses_net": expenses,
        "result_net": money(income - expenses),
        "accounts": accounts,
    }



@router.get("/eur/pdf")
def download_eur_pdf(
    db: DatabaseSession,
    user: TenantUser,
    year: int = Query(ge=2000, le=2099),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    sort_by: str = Query(default="date"),
    group_by: str = Query(default="account"),
    view: str = Query(default="details"),
):
    """Exportiert die vorhandene mandantenbezogene EÜR als PDF."""
    from fastapi.responses import Response
    from app.services.eur_pdf import render_eur_pdf

    if view not in {"summary", "details"}:
        raise HTTPException(422, "Ungueltige PDF-Darstellung.")

    data = annual_eur(
        db=db,
        user=user,
        year=year,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        group_by=group_by,
    )

    pdf = render_eur_pdf(data, view=view)

    filename = (
        f"EUR_{data['date_from']}_{data['date_to']}_"
        f"{view}.pdf"
    )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )



def calculate_bank_balance(db, tenant_id, opening_date, opening_balance, target_date):
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
        .where(Invoice.tenant_id == tenant_id)
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
