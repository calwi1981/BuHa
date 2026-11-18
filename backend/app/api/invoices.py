import re
from uuid import uuid4
from sqlalchemy import text
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DatabaseSession, TenantUser
from app.models.account import Account
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.partner import Partner
from app.models.product import Product
from app.models.payment import Payment
from app.models.payment_account import PaymentAccount

router = APIRouter(prefix="/api/invoices", tags=["Rechnungen"])

CENT = Decimal("0.01")


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


class LineData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str = Field(default="Stueck", max_length=30)
    unit_net_price: Decimal = Field(
        ge=0, max_digits=14, decimal_places=4
    )
    vat_rate: Decimal = Field(
        ge=0, le=100, max_digits=5, decimal_places=2
    )
    discount_type: str = "none"
    discount_value: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    account_id: int | None = None
    product_id: int | None = None


    @model_validator(mode="after")
    def check_discount(self):
        if self.discount_type not in {"none", "percent", "fixed"}:
            raise ValueError("Ungueltige Rabattart.")

        if self.discount_type == "percent":
            if self.discount_value > 100:
                raise ValueError("Prozentrabatt ueber 100 Prozent.")

        if self.discount_type == "none" and self.discount_value != 0:
            raise ValueError("Rabattwert ohne Rabattart.")

        base = money(self.quantity * self.unit_net_price)

        if self.discount_type == "fixed":
            if self.discount_value > base:
                raise ValueError("Festrabatt ueber Positionswert.")

        return self
    utility_total_cost: Decimal | None = None
    utility_total_key: Decimal | None = None
    utility_tenant_key: Decimal | None = None


class InvoiceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_number: str | None = None
    supplier_reference: str | None = Field(
        default=None, max_length=100
    )
    invoice_type: str
    partner_id: int
    invoice_date: date
    due_date: date | None = None
    notes: str | None = None
    xrechnung_enabled: bool = False
    xrechnung_buyer_reference: str | None = Field(
        default=None, max_length=255
    )
    lines: list[LineData] = Field(min_length=1)

    @model_validator(mode="after")
    def check_dates(self):
        if self.due_date and self.due_date < self.invoice_date:
            raise ValueError("Faelligkeit liegt vor Rechnungsdatum.")
        return self
    utility_period_from: date | None = None
    utility_period_to: date | None = None
    utility_prepayments: Decimal | None = None
    utility_account_id: int | None = None


class PaymentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_account_id: int = Field(gt=0)
    payment_date: date
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    payment_method: str = Field(min_length=1, max_length=30)
    reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None


def payable_invoice_total(invoice):
    """Zahlbarer Betrag; Vorauszahlungen sind keine Rabatte."""
    if invoice.utility_period_from is not None:
        difference = invoice.utility_difference
        if difference is None:
            raise HTTPException(
                422, "Nebenkostenabrechnung ist unvollstaendig."
            )
        return money(max(Decimal("0"), Decimal(str(difference))))

    return money(invoice.gross_total)


def serialize_invoice(db, invoice):
    lines = db.scalars(
        select(InvoiceLine)
        .where(InvoiceLine.invoice_id == invoice.id)
        .order_by(InvoiceLine.position)
    ).all()

    payments = db.scalars(
        select(Payment)
        .where(Payment.invoice_id == invoice.id)
        .order_by(Payment.payment_date, Payment.id)
    ).all()

    paid = money(sum((p.amount for p in payments), Decimal("0")))

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_type": invoice.invoice_type,
        "supplier_reference": invoice.supplier_reference,
        "partner_id": invoice.partner_id,
        "invoice_date": invoice.invoice_date,
        "due_date": invoice.due_date,
        "status": invoice.status,
        "currency": invoice.currency,
        "net_total": invoice.net_total,
        "vat_total": invoice.vat_total,
        "gross_total": invoice.gross_total,
        "paid_total": paid,
        "open_total": money(
            (
                invoice.utility_difference
                if invoice.utility_period_from is not None
                else invoice.gross_total
            ) - paid
        ),
        "utility_account_id": invoice.utility_account_id,
        "utility_period_from": invoice.utility_period_from,
        "utility_period_to": invoice.utility_period_to,
        "utility_prepayments": invoice.utility_prepayments,
        "utility_total_cost": invoice.utility_total_cost,
        "utility_difference": invoice.utility_difference,
        "utility_credit_total": (
            money(-invoice.utility_difference)
            if invoice.utility_period_from is not None
            and invoice.utility_difference is not None
            and invoice.utility_difference < 0
            else Decimal("0.00")
        ),
        "notes": invoice.notes,
        "xrechnung_enabled": invoice.xrechnung_enabled,
        "xrechnung_buyer_reference": invoice.xrechnung_buyer_reference,
        "lines": [
            {
                column.name: getattr(line, column.name)
                for column in line.__table__.columns
            }
            for line in lines
        ],
        "payments": [
            {
                column.name: getattr(payment, column.name)
                for column in payment.__table__.columns
            }
            for payment in payments
        ],
    }


@router.get("")
def list_invoices(
    db: DatabaseSession,
    user: CurrentUser,
    tenant: TenantUser,
):
    invoices = db.scalars(
        select(Invoice)
        .where(Invoice.tenant_id == tenant.tenant_id)
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    ).all()

    return [serialize_invoice(db, invoice) for invoice in invoices]


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: int,
    db: DatabaseSession,
    user: CurrentUser,
    tenant: TenantUser,
):
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant.tenant_id,
        )
    )

    if invoice is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    return serialize_invoice(db, invoice)


@router.post("", status_code=201)
def create_invoice(
    data: InvoiceData,
    db: DatabaseSession,
    user: CurrentUser,
    tenant: TenantUser,
):
    if data.invoice_type not in {"outgoing", "incoming"}:
        raise HTTPException(422, "Ungueltige Rechnungsart.")

    partner = db.get(Partner, data.partner_id)

    if partner is None or partner.tenant_id != tenant.tenant_id or not partner.is_active:
        raise HTTPException(422, "Geschaeftspartner nicht vorhanden.")

    if data.invoice_type == "outgoing" and not partner.is_customer:
        raise HTTPException(422, "Partner ist kein Kunde.")

    if data.invoice_type == "incoming" and not partner.is_supplier:
        raise HTTPException(422, "Partner ist kein Lieferant.")

    for line in data.lines:
        if line.product_id is not None:
            product = db.get(Product, line.product_id)
            if product is None or product.tenant_id != tenant.tenant_id or not product.is_active:
                raise HTTPException(
                    422, "Produkt nicht vorhanden oder inaktiv."
                )

        if line.account_id is not None:
            account = db.get(Account, line.account_id)
            expected_type = (
                "income" if data.invoice_type == "outgoing" else "expense"
            )

            if (
                account is None
                or account.tenant_id != tenant.tenant_id
                or not account.is_active
                or account.account_type != expected_type
            ):
                raise HTTPException(422, "Unpassendes Buchungskonto.")


    # Nebenkosten werden nur bei entsprechend gekennzeichneten
    # Ausgangsrechnungen berechnet.
    utility_requested = any((
        data.utility_period_from is not None,
        data.utility_period_to is not None,
        data.utility_prepayments is not None,
        any(
            line.utility_total_cost is not None
            or line.utility_total_key is not None
            or line.utility_tenant_key is not None
            for line in data.lines
        ),
    ))

    utility_result = None

    if utility_requested:
        if data.invoice_type != "outgoing":
            raise HTTPException(
                422, "Nebenkosten nur für Ausgangsrechnungen."
            )

        if (
            data.utility_period_from is None
            or data.utility_period_to is None
            or data.utility_period_from > data.utility_period_to
        ):
            raise HTTPException(
                422, "Ungültiger Nebenkosten-Abrechnungszeitraum."
            )

        if data.utility_prepayments is None:
            raise HTTPException(
                422, "Vorauszahlungen müssen angegeben werden."
            )

        from app.services.utility_calculation import (
            calculate_utility_statement,
        )

        try:
            utility_result = calculate_utility_statement(
                [
                    {
                        "description": line.description,
                        "total_cost": line.utility_total_cost,
                        "total_key": line.utility_total_key,
                        "tenant_key": line.utility_tenant_key,
                    }
                    for line in data.lines
                ],
                data.utility_prepayments,
            )
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            raise HTTPException(422, str(exc)) from exc

        for line, calculated in zip(
            data.lines, utility_result["positions"]
        ):
            if (
                money(line.quantity * line.unit_net_price)
                != calculated["tenant_share"]
            ):
                raise HTTPException(
                    422,
                    "Der Rechnungspositionsbetrag muss dem "
                    "berechneten Nebenkostenanteil entsprechen."
                )


    if utility_requested:
        if data.utility_account_id is None:
            raise HTTPException(
                422, "NK-Buchungskonto ist erforderlich."
            )
        utility_account = db.scalar(
            select(Account).where(
                Account.id == data.utility_account_id,
                Account.tenant_id == tenant.tenant_id,
                Account.is_active.is_(True),
                Account.account_type == "income",
            )
        )
        if utility_account is None:
            raise HTTPException(
                422, "Ungueltiges NK-Einnahmenkonto."
            )
    elif data.utility_account_id is not None:
        raise HTTPException(
            422, "NK-Buchungskonto nur fuer Nebenkostenabrechnungen."
        )

    invoice = Invoice(
        utility_account_id=(
            data.utility_account_id if utility_requested else None
        ),
        utility_period_from=(
            data.utility_period_from if utility_requested else None
        ),
        utility_period_to=(
            data.utility_period_to if utility_requested else None
        ),
        utility_prepayments=(
            utility_result["prepayments"]
            if utility_result is not None else None
        ),
        utility_total_cost=(
            utility_result["total_tenant_cost"]
            if utility_result is not None else None
        ),
        utility_difference=(
            utility_result["difference"]
            if utility_result is not None else None
        ),

        tenant_id=tenant.tenant_id,
        invoice_number="DRAFT-" + uuid4().hex,
        supplier_reference=data.supplier_reference
        if data.invoice_type == "incoming" else None,
        invoice_type=data.invoice_type,
        partner_id=data.partner_id,
        invoice_date=data.invoice_date,
        due_date=data.due_date,
        status="draft",
        currency="EUR",
        net_total=Decimal("0"),
        vat_total=Decimal("0"),
        gross_total=Decimal("0"),
        notes=data.notes,
        xrechnung_enabled=(
            data.xrechnung_enabled
            if data.invoice_type == "outgoing" else False
        ),
        xrechnung_buyer_reference=(
            data.xrechnung_buyer_reference
            if data.invoice_type == "outgoing" else None
        ),
    )

    db.add(invoice)

    try:
        db.flush()

        net_total = Decimal("0")
        vat_total = Decimal("0")

        for position, line in enumerate(data.lines, start=1):
            base_net = money(
                line.quantity * line.unit_net_price
            )

            if line.discount_type == "percent":
                discount = money(
                    base_net * line.discount_value / Decimal("100")
                )
            elif line.discount_type == "fixed":
                discount = money(line.discount_value)
            else:
                discount = Decimal("0.00")

            net = money(base_net - discount)
            vat = money(net * line.vat_rate / Decimal("100"))
            gross = money(net + vat)

            db.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    position=position,
                    product_id=line.product_id,
                    description=line.description,
                    quantity=line.quantity,
                    unit=line.unit,
                    unit_net_price=line.unit_net_price,
                    vat_rate=line.vat_rate,
                    discount_type=line.discount_type,
                    discount_value=line.discount_value,
                    account_id=line.account_id,
                    utility_total_cost=(
                        line.utility_total_cost
                        if utility_requested else None
                    ),
                    utility_total_key=(
                        line.utility_total_key
                        if utility_requested else None
                    ),
                    utility_tenant_key=(
                        line.utility_tenant_key
                        if utility_requested else None
                    ),
                    net_total=net,
                    vat_total=vat,
                    gross_total=gross,
                )
            )

            net_total += net
            vat_total += vat

        invoice.net_total = money(net_total)
        invoice.vat_total = money(vat_total)
        invoice.gross_total = money(net_total + vat_total)

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Rechnungsnummer bereits vorhanden oder Referenz ungueltig.",
        )

    db.refresh(invoice)
    return serialize_invoice(db, invoice)




def next_invoice_number(db, invoice):
    db.execute(text("SELECT pg_advisory_xact_lock(127001)"))

    year = invoice.invoice_date.year
    outgoing = invoice.invoice_type == "outgoing"

    settings = db.execute(
        text("SELECT settings FROM company_settings WHERE tenant_id=:tenant_id"), {"tenant_id": invoice.tenant_id}
    ).scalar_one_or_none() or {}


    if outgoing and invoice.utility_period_from is not None:
        partner = db.get(Partner, invoice.partner_id)
        if partner is None or partner.tenant_id != invoice.tenant_id:
            raise HTTPException(422, "Mieter nicht vorhanden.")

        prefix = settings.get("utility_invoice_prefix", "NK")
        digits = int(settings.get("utility_invoice_digits", 1))
        minimum = int(settings.get("utility_invoice_next", 1))
        year = invoice.utility_period_to.year

        partner_number = str(partner.partner_number).strip()
        if not partner_number or len(partner_number) > 50 or any(ord(char) < 32 or ord(char) == 127 for char in partner_number):
            raise HTTPException(
                422, "Mieternummer enthält unzulässige Zeichen."
            )

        stem = f"{prefix}-{year}-{partner_number}-"
        kind = "utility"

        row = db.execute(
            text("""
                SELECT last_number FROM invoice_sequences
                WHERE tenant_id=:tenant_id
                  AND invoice_type=:kind
                  AND year=:year
                FOR UPDATE
            """),
            {
                "tenant_id": invoice.tenant_id,
                "kind": kind,
                "year": year,
            },
        ).first()

        last = row[0] if row else 0
        candidate = max(last + 1, minimum)

        while True:
            number = stem + str(candidate).zfill(digits)
            occupied = db.execute(
                text("""
                    SELECT 1 FROM invoices
                    WHERE tenant_id=:tenant_id
                      AND invoice_number=:number
                    UNION ALL
                    SELECT 1 FROM manual_bookings
                    WHERE tenant_id=:tenant_id
                      AND booking_number=:number
                """),
                {
                    "tenant_id": invoice.tenant_id,
                    "number": number,
                },
            ).first()

            if not occupied:
                break
            candidate += 1

        db.execute(
            text("""
                INSERT INTO invoice_sequences
                    (tenant_id, invoice_type, year, last_number)
                VALUES (:tenant_id, :kind, :year, :number)
                ON CONFLICT (tenant_id, invoice_type, year)
                DO UPDATE SET last_number=EXCLUDED.last_number
            """),
            {
                "tenant_id": invoice.tenant_id,
                "kind": kind,
                "year": year,
                "number": candidate,
            },
        )

        return number

    if outgoing:
        prefix = settings.get("invoice_prefix", "RE")
        digits = int(settings.get("invoice_digits", 4))
        separator = "-"
        minimum = int(settings.get("invoice_next", 1))
    else:
        prefix = settings.get("incoming_prefix", "LR")
        digits = int(settings.get("incoming_digits", 3))
        separator = ""
        minimum = int(settings.get("incoming_next", 1))

    stem = f"{prefix}{year % 100:02d}{separator}"

    row = db.execute(
        text("""
            SELECT last_number
            FROM invoice_sequences
            WHERE tenant_id=:tenant_id AND invoice_type=:kind AND year=:year
            FOR UPDATE
        """),
        {"tenant_id": invoice.tenant_id, "kind": invoice.invoice_type, "year": year},
    ).first()

    last = row[0] if row else 0

    existing = db.execute(
        text("""
            SELECT invoice_number
            FROM invoices
            WHERE tenant_id=:tenant_id AND invoice_number LIKE :pattern
        """),
        {"tenant_id": invoice.tenant_id, "pattern": stem + "%"},
    ).scalars().all()

    for number in existing:
        match = re.fullmatch(
            re.escape(stem) + r"(\\d+)", number
        )
        if match:
            last = max(last, int(match.group(1)))

    candidate = max(last + 1, minimum)

    while True:
        number = stem + str(candidate).zfill(digits)
        occupied = db.execute(
            text("""
                SELECT 1 FROM invoices
                WHERE tenant_id=:tenant_id AND invoice_number=:number
                UNION ALL
                SELECT 1 FROM manual_bookings
                WHERE tenant_id=:tenant_id AND booking_number=:number
            """),
            {"tenant_id": invoice.tenant_id, "number": number},
        ).first()
        if not occupied:
            break
        candidate += 1

    db.execute(
        text("""
            INSERT INTO invoice_sequences
                (tenant_id, invoice_type, year, last_number)
            VALUES (:tenant_id, :kind, :year, :number)
            ON CONFLICT (tenant_id, invoice_type, year)
            DO UPDATE SET last_number=EXCLUDED.last_number
        """),
        {
            "tenant_id": invoice.tenant_id,
            "kind": invoice.invoice_type,
            "year": year,
            "number": candidate,
        },
    )

    return number




def finalize_invoice_core(db, invoice):
    """Gemeinsame Rechnungsfreigabe ohne E-Mail-Versand."""
    if invoice.gross_total <= 0:
        raise HTTPException(422, "Rechnungsbetrag muss positiv sein.")

    invoice.invoice_number = next_invoice_number(db, invoice)

    if invoice.utility_period_from is not None:
        if invoice.utility_difference is None:
            raise HTTPException(
                422, "Nebenkostenabrechnung ist unvollstaendig."
            )
        # Jede freigegebene Nebenkostenabrechnung bleibt offen,
        # bis der Zahlungsausgleich tatsächlich gebucht wurde.
        invoice.status = "open"
    else:
        invoice.status = "open"

    if (
        invoice.invoice_type == "outgoing"
        and getattr(invoice, "xrechnung_enabled", False)
    ):
        from app.api.administration import load_settings
        from app.services.xrechnung.ubl_export import (
            generate_ubl_invoice,
        )
        from app.services.xrechnung.validator import (
            validate_xrechnung,
        )

        try:
            partner = db.get(Partner, invoice.partner_id)
            lines = db.scalars(
                select(InvoiceLine)
                .where(InvoiceLine.invoice_id == invoice.id)
                .order_by(InvoiceLine.position)
            ).all()

            xml = generate_ubl_invoice(
                invoice,
                partner,
                lines,
                load_settings(db, invoice.tenant_id),
            )
            validate_xrechnung(xml)

        except Exception as error:
            db.rollback()
            raise HTTPException(
                422,
                "XRechnung konnte nicht validiert werden: "
                + str(error),
            ) from error




@router.post("/{invoice_id}/finalize")
def finalize_invoice(
    invoice_id: int,
    db: DatabaseSession,
    user: CurrentUser,
    tenant: TenantUser,
):
    invoice = db.execute(
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant.tenant_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if invoice is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    if invoice.status != "draft":
        raise HTTPException(409, "Rechnung bereits freigegeben.")

    finalize_invoice_core(db, invoice)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Rechnungsnummer bereits vergeben.")

    # BUHA_AUTO_MAIL_168
    result = serialize_invoice(db, invoice)

    if invoice.invoice_type == "outgoing":
        from app.api.administration import load_settings
        from app.services.invoice_email import deliver_invoice_email

        try:
            settings = load_settings(db, tenant.tenant_id)
            auto_send = settings.get(
                "invoice_auto_send_enabled", False
            ) is True

            if auto_send:
                result["email_delivery"] = deliver_invoice_email(
                    db,
                    invoice.id,
                    tenant_id=tenant.tenant_id,
                    delivery_type="automatic",
                )
            else:
                result["email_delivery"] = {
                    "status": "disabled",
                    "ok": False,
                }

        except Exception:
            db.rollback()
            result["email_delivery"] = {
                "status": "failed",
                "ok": False,
                "error": (
                    "Rechnung freigegeben. "
                    "Automatischer E-Mail-Versand fehlgeschlagen."
                ),
            }

    return result



@router.post("/{invoice_id}/send-xrechnung")
def send_invoice_xrechnung(
    invoice_id: int,
    db: DatabaseSession,
    user: CurrentUser,
    tenant: TenantUser,
):
    from app.services.invoice_email import deliver_invoice_email

    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant.tenant_id,
        )
    )

    if invoice is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    if invoice.invoice_type != "outgoing":
        raise HTTPException(422, "Nur Ausgangsrechnungen.")

    if invoice.status == "draft":
        raise HTTPException(409, "Rechnung nicht freigegeben.")

    result = deliver_invoice_email(
        db,
        invoice_id,
        tenant_id=tenant.tenant_id,
        delivery_type="manual",
        force_xrechnung=True,
    )

    if not result.get("ok"):
        raise HTTPException(
            422,
            result.get("error") or "XRechnung-Versand fehlgeschlagen.",
        )

    return result


@router.post("/{invoice_id}/payments", status_code=201)
def add_payment(
    invoice_id: int,
    data: PaymentData,
    db: DatabaseSession,
    user: CurrentUser,
    tenant: TenantUser,
):
    invoice = db.execute(
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant.tenant_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if invoice is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    if invoice.status not in {"open", "partial"}:
        raise HTTPException(409, "Rechnung ist nicht zahlbar.")

    payment_account = db.scalar(
        select(PaymentAccount).where(
            PaymentAccount.id == data.payment_account_id,
            PaymentAccount.tenant_id == tenant.tenant_id,
            PaymentAccount.is_active.is_(True),
        )
    )

    if payment_account is None:
        raise HTTPException(
            422,
            "Zahlungskonto nicht gefunden, inaktiv oder "
            "nicht diesem Mandanten zugeordnet.",
        )

    payments = db.scalars(
        select(Payment).where(Payment.invoice_id == invoice_id)
    ).all()

    total_paid = sum(
        (payment.amount for payment in payments),
        Decimal("0"),
    )

    is_utility = invoice.utility_period_from is not None

    if is_utility:
        if invoice.utility_difference is None:
            raise HTTPException(
                422, "Nebenkostenabrechnung unvollstaendig."
            )

        target = money(invoice.utility_difference)
        new_paid = money(total_paid + data.amount)

        if target > 0:
            if data.amount <= 0:
                raise HTTPException(
                    422, "Nachzahlung erfordert einen Zahlungseingang."
                )
            if new_paid > target:
                raise HTTPException(
                    422, "Zahlung uebersteigt Nachzahlung."
                )

        elif target < 0:
            if data.amount >= 0:
                raise HTTPException(
                    422, "Guthaben erfordert eine Auszahlung."
                )
            if new_paid < target:
                raise HTTPException(
                    422, "Auszahlung uebersteigt Guthaben."
                )

        else:
            if data.amount != 0 or total_paid != 0:
                raise HTTPException(
                    422, "Nullsaldo erlaubt nur einen Ausgleich."
                )
    else:
        if data.amount <= 0:
            raise HTTPException(
                422, "Zahlungsbetrag muss positiv sein."
            )
        if money(total_paid + data.amount) > invoice.gross_total:
            raise HTTPException(
                422, "Zahlung uebersteigt offenen Betrag."
            )

    payment = Payment(
        invoice_id=invoice.id,
        **data.model_dump(),
    )

    db.add(payment)

    new_paid = money(total_paid + data.amount)
    target = (
        money(invoice.utility_difference)
        if invoice.utility_period_from is not None
        else money(invoice.gross_total)
    )
    invoice.status = "paid" if new_paid == target else "partial"

    db.commit()

    return serialize_invoice(db, invoice)


@router.put("/{invoice_id}")
def update_invoice_draft(
    invoice_id: int,
    data: InvoiceData,
    db: DatabaseSession,
    user: CurrentUser,
    tenant: TenantUser,
):
    invoice = db.execute(
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant.tenant_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if invoice is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    if invoice.status != "draft":
        raise HTTPException(
            409,
            "Nur Rechnungsentwürfe dürfen bearbeitet werden.",
        )

    if data.invoice_type != invoice.invoice_type:
        raise HTTPException(
            422,
            "Die Rechnungsart darf nicht geändert werden.",
        )

    partner = db.get(Partner, data.partner_id)

    if partner is None or partner.tenant_id != tenant.tenant_id or not partner.is_active:
        raise HTTPException(422, "Geschaeftspartner nicht vorhanden.")

    if data.invoice_type == "outgoing" and not partner.is_customer:
        raise HTTPException(422, "Partner ist kein Kunde.")

    if data.invoice_type == "incoming" and not partner.is_supplier:
        raise HTTPException(422, "Partner ist kein Lieferant.")

    # Nebenkosten werden nur bei entsprechend gekennzeichneten
    # Ausgangsrechnungen berechnet.
    utility_requested = any((
        data.utility_period_from is not None,
        data.utility_period_to is not None,
        data.utility_prepayments is not None,
        any(
            line.utility_total_cost is not None
            or line.utility_total_key is not None
            or line.utility_tenant_key is not None
            for line in data.lines
        ),
    ))

    utility_result = None

    if utility_requested:
        if data.invoice_type != "outgoing":
            raise HTTPException(
                422, "Nebenkosten nur für Ausgangsrechnungen."
            )

        if (
            data.utility_period_from is None
            or data.utility_period_to is None
            or data.utility_period_from > data.utility_period_to
        ):
            raise HTTPException(
                422, "Ungültiger Nebenkosten-Abrechnungszeitraum."
            )

        if data.utility_prepayments is None:
            raise HTTPException(
                422, "Vorauszahlungen müssen angegeben werden."
            )

        from app.services.utility_calculation import (
            calculate_utility_statement,
        )

        try:
            utility_result = calculate_utility_statement(
                [
                    {
                        "description": line.description,
                        "total_cost": line.utility_total_cost,
                        "total_key": line.utility_total_key,
                        "tenant_key": line.utility_tenant_key,
                    }
                    for line in data.lines
                ],
                data.utility_prepayments,
            )
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            raise HTTPException(422, str(exc)) from exc

        for line, calculated in zip(
            data.lines, utility_result["positions"]
        ):
            if (
                money(line.quantity * line.unit_net_price)
                != calculated["tenant_share"]
            ):
                raise HTTPException(
                    422,
                    "Der Rechnungspositionsbetrag muss dem "
                    "berechneten Nebenkostenanteil entsprechen."
                )


    if utility_requested:
        if data.utility_account_id is None:
            raise HTTPException(
                422, "NK-Buchungskonto ist erforderlich."
            )
        utility_account = db.scalar(
            select(Account).where(
                Account.id == data.utility_account_id,
                Account.tenant_id == tenant.tenant_id,
                Account.is_active.is_(True),
                Account.account_type == "income",
            )
        )
        if utility_account is None:
            raise HTTPException(
                422, "Ungueltiges NK-Einnahmenkonto."
            )
    elif data.utility_account_id is not None:
        raise HTTPException(
            422, "NK-Buchungskonto nur fuer Nebenkostenabrechnungen."
        )

    existing_lines = db.scalars(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
    ).all()

    existing_product_ids = {
        line.product_id for line in existing_lines
        if line.product_id is not None
    }
    existing_account_ids = {
        line.account_id for line in existing_lines
        if line.account_id is not None
    }

    for line in data.lines:
        if line.product_id is not None:
            product = db.get(Product, line.product_id)
            if (
                product is None
                or product.tenant_id != tenant.tenant_id
                or (
                    not product.is_active
                    and line.product_id not in existing_product_ids
                )
            ):
                raise HTTPException(
                    422, "Produkt nicht vorhanden oder inaktiv."
                )

        if line.account_id is not None:
            account = db.get(Account, line.account_id)
            expected_type = (
                "income" if data.invoice_type == "outgoing" else "expense"
            )

            if (
                account is None
                or account.tenant_id != tenant.tenant_id
                or (
                    not account.is_active
                    and line.account_id not in existing_account_ids
                )
                or account.account_type != expected_type
            ):
                raise HTTPException(422, "Unpassendes Buchungskonto.")


    invoice.utility_account_id = (
        data.utility_account_id if utility_requested else None
    )
    invoice.utility_period_from = (
        data.utility_period_from if utility_requested else None
    )
    invoice.utility_period_to = (
        data.utility_period_to if utility_requested else None
    )
    invoice.utility_prepayments = (
        utility_result["prepayments"]
        if utility_result is not None else None
    )
    invoice.utility_total_cost = (
        utility_result["total_tenant_cost"]
        if utility_result is not None else None
    )
    invoice.utility_difference = (
        utility_result["difference"]
        if utility_result is not None else None
    )

    invoice.partner_id = data.partner_id
    invoice.invoice_date = data.invoice_date
    invoice.due_date = data.due_date
    invoice.notes = data.notes
    invoice.xrechnung_enabled = (
        data.xrechnung_enabled
        if data.invoice_type == "outgoing" else False
    )
    invoice.xrechnung_buyer_reference = (
        data.xrechnung_buyer_reference
        if data.invoice_type == "outgoing" else None
    )
    invoice.supplier_reference = (
        data.supplier_reference
        if data.invoice_type == "incoming"
        else None
    )

    try:
        db.execute(
            text(
                "DELETE FROM invoice_lines "
                "WHERE invoice_id = :invoice_id"
            ),
            {"invoice_id": invoice.id},
        )

        net_total = Decimal("0")
        vat_total = Decimal("0")

        for position, line in enumerate(data.lines, start=1):
            base_net = money(
                line.quantity * line.unit_net_price
            )

            if line.discount_type == "percent":
                discount = money(
                    base_net * line.discount_value / Decimal("100")
                )
            elif line.discount_type == "fixed":
                discount = money(line.discount_value)
            else:
                discount = Decimal("0.00")

            net = money(base_net - discount)
            vat = money(net * line.vat_rate / Decimal("100"))
            gross = money(net + vat)

            db.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    position=position,
                    product_id=line.product_id,
                    description=line.description,
                    quantity=line.quantity,
                    unit=line.unit,
                    unit_net_price=line.unit_net_price,
                    vat_rate=line.vat_rate,
                    discount_type=line.discount_type,
                    discount_value=line.discount_value,
                    account_id=line.account_id,
                    utility_total_cost=(
                        line.utility_total_cost
                        if utility_requested else None
                    ),
                    utility_total_key=(
                        line.utility_total_key
                        if utility_requested else None
                    ),
                    utility_tenant_key=(
                        line.utility_tenant_key
                        if utility_requested else None
                    ),
                    net_total=net,
                    vat_total=vat,
                    gross_total=gross,
                )
            )

            net_total += net
            vat_total += vat

        invoice.net_total = money(net_total)
        invoice.vat_total = money(vat_total)
        invoice.gross_total = money(net_total + vat_total)

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Rechnungsentwurf konnte nicht gespeichert werden.",
        )

    db.refresh(invoice)
    return serialize_invoice(db, invoice)
