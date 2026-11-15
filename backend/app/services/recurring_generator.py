"""Erzeugung wiederkehrender Rechnungsentwuerfe.

Keine automatische Ausfuehrung und kein E-Mail-Versand.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import select, text

from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.partner import Partner
from app.models.product import Product

CENT = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )


def create_recurring_draft(db, template_id, scheduled_date):
    """Erstellt genau einen Entwurf je Vorlage und Termin.

    Der Aufrufer muss die Transaktion abschliessen.
    """

    template = db.execute(
        text("""
            SELECT *
            FROM recurring_invoices
            WHERE id = :id
            FOR UPDATE
        """),
        {"id": template_id},
    ).mappings().first()

    if template is None:
        raise ValueError("Wiederkehrende Vorlage nicht gefunden.")

    if not template["is_active"]:
        raise ValueError("Wiederkehrende Vorlage ist inaktiv.")

    existing = db.execute(
        text("""
            SELECT id, invoice_id
            FROM recurring_invoice_runs
            WHERE recurring_invoice_id = :id
              AND scheduled_date = :scheduled_date
        """),
        {
            "id": template_id,
            "scheduled_date": scheduled_date,
        },
    ).mappings().first()

    if existing is not None:
        return {
            "created": False,
            "run_id": existing["id"],
            "invoice_id": existing["invoice_id"],
        }

    partner = db.get(Partner, template["partner_id"])

    if (
        partner is None
        or not partner.is_active
        or not partner.is_customer
    ):
        raise ValueError("Kunde ist nicht mehr gueltig.")

    positions = db.execute(
        text("""
            SELECT product_id, quantity, position
            FROM recurring_invoice_lines
            WHERE recurring_invoice_id = :id
            ORDER BY position
        """),
        {"id": template_id},
    ).mappings().all()

    if not positions:
        raise ValueError("Vorlage enthaelt keine Positionen.")

    prepared = []

    for position in positions:
        product = db.get(Product, position["product_id"])

        if product is None or not product.is_active:
            raise ValueError(
                "Ein Artikel ist nicht mehr vorhanden oder inaktiv."
            )

        quantity = Decimal(str(position["quantity"]))
        unit_price = Decimal(str(product.net_price))
        vat_rate = Decimal(str(product.vat_rate))

        net = money(quantity * unit_price)
        vat = money(net * vat_rate / Decimal("100"))
        gross = money(net + vat)

        prepared.append({
            "position": position["position"],
            "product": product,
            "quantity": quantity,
            "unit_price": unit_price,
            "vat_rate": vat_rate,
            "net": net,
            "vat": vat,
            "gross": gross,
        })

    invoice = Invoice(
        invoice_number="DRAFT-" + uuid4().hex,
        invoice_type="outgoing",
        partner_id=partner.id,
        invoice_date=scheduled_date,
        due_date=scheduled_date + timedelta(
            days=template["due_days"]
        ),
        status="draft",
        currency="EUR",
        notes=template["notes"],
        xrechnung_enabled=template["xrechnung_enabled"],
        xrechnung_buyer_reference=(
            template["xrechnung_buyer_reference"]
            or partner.xrechnung_buyer_reference
        ),
        net_total=money(
            sum((p["net"] for p in prepared), Decimal("0"))
        ),
        vat_total=money(
            sum((p["vat"] for p in prepared), Decimal("0"))
        ),
        gross_total=money(
            sum((p["gross"] for p in prepared), Decimal("0"))
        ),
    )

    db.add(invoice)
    db.flush()

    for item in prepared:
        product = item["product"]

        db.add(InvoiceLine(
            invoice_id=invoice.id,
            position=item["position"],
            product_id=product.id,
            description=product.description or product.name,
            quantity=item["quantity"],
            unit=product.unit,
            unit_net_price=item["unit_price"],
            vat_rate=item["vat_rate"],
            discount_type="none",
            discount_value=Decimal("0"),
            account_id=product.revenue_account_id,
            net_total=item["net"],
            vat_total=item["vat"],
            gross_total=item["gross"],
        ))

    db.flush()

    run_id = db.execute(
        text("""
            INSERT INTO recurring_invoice_runs (
                recurring_invoice_id,
                scheduled_date,
                invoice_id,
                status
            )
            VALUES (
                :template_id,
                :scheduled_date,
                :invoice_id,
                'pending'
            )
            RETURNING id
        """),
        {
            "template_id": template_id,
            "scheduled_date": scheduled_date,
            "invoice_id": invoice.id,
        },
    ).scalar_one()

    return {
        "created": True,
        "run_id": run_id,
        "invoice_id": invoice.id,
    }
