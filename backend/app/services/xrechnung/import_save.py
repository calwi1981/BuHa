"""Atomare Speicherung einer geprüften XRechnung als Eingangsrechnungsentwurf."""

import hashlib
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.account import Account
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.partner import Partner
from app.models.xrechnung_document import XRechnungDocument

from app.services.xrechnung.import_checks import check_duplicate
from app.services.xrechnung.import_prepare import (
    XRechnungImportError,
    prepare_import,
)


def save_incoming_xrechnung(
    db,
    *,
    parsed,
    xml_content,
    original_filename,
    partner_id,
    account_id,
):
    """Speichert nur bereits extern validierte Rechnungsdaten.

    Der Aufrufer muss die XML-Datei unmittelbar zuvor erneut parsen
    und mit KoSIT validieren. Ein clientseitiges Preview-Ergebnis
    darf nicht als vertrauenswürdige Eingabe verwendet werden.
    """

    if not isinstance(xml_content, bytes) or not xml_content:
        raise XRechnungImportError("Original-XML fehlt.")

    if len(xml_content) > 10 * 1024 * 1024:
        raise XRechnungImportError("XML-Datei überschreitet 10 MB.")

    if not original_filename or len(original_filename) > 255:
        raise XRechnungImportError("Ungültiger XML-Dateiname.")

    prepared = prepare_import(parsed)

    try:
        partner_id = int(partner_id)
        account_id = int(account_id)
    except (TypeError, ValueError) as exc:
        raise XRechnungImportError(
            "Lieferanten-ID oder Buchungskonto ungültig."
        ) from exc

    partner = db.get(Partner, partner_id)

    if (
        partner is None
        or not partner.is_active
        or not partner.is_supplier
    ):
        raise XRechnungImportError(
            "Der ausgewählte Lieferant ist nicht aktiv oder ungültig."
        )

    account = db.get(Account, account_id)

    if (
        account is None
        or not account.is_active
        or account.account_type != "expense"
    ):
        raise XRechnungImportError(
            "Es muss ein aktives Aufwandskonto ausgewählt werden."
        )

    # Transaktionsbezogene PostgreSQL-Sperre:
    # Verhindert parallele Importe derselben Lieferanten-Rechnungsnummer.
    from sqlalchemy import text

    lock_key = (
        f"buha:xrechnung:{partner.id}:"
        f"{prepared['supplier_reference']}"
    )

    xml_hash = hashlib.sha256(xml_content).hexdigest()

    try:
        # Beide Sperren in fester Reihenfolge erwerben.
        # Die Hash-Sperre verhindert parallele Importe derselben XML.
        for key in sorted((lock_key, "buha:xrechnung:sha256:" + xml_hash)):
            db.execute(
                text(
                    "SELECT pg_advisory_xact_lock("
                    "hashtextextended(:key, 0))"
                ),
                {"key": key},
            )

        duplicate = check_duplicate(
            db,
            partner.id,
            prepared["supplier_reference"],
        )

        if duplicate["duplicate"]:
            raise XRechnungImportError(
                "Diese Lieferanten-Rechnungsnummer ist bereits vorhanden."
            )

        existing_document = db.scalar(
            select(XRechnungDocument).where(
                XRechnungDocument.sha256 == xml_hash
            )
        )

        if existing_document is not None:
            raise XRechnungImportError(
                "Diese Original-XML wurde bereits importiert."
            )

    except Exception:
        db.rollback()
        raise

    invoice = Invoice(
        invoice_number="DRAFT-" + uuid4().hex,
        invoice_type="incoming",
        supplier_reference=prepared["supplier_reference"],
        partner_id=partner.id,
        invoice_date=prepared["invoice_date"],
        due_date=prepared["due_date"],
        status="draft",
        currency="EUR",
        net_total=prepared["net_total"],
        vat_total=prepared["vat_total"],
        gross_total=prepared["gross_total"],
        notes="Import aus elektronischer Rechnung",
        xrechnung_enabled=False,
        xrechnung_buyer_reference=None,
    )

    try:
        db.add(invoice)
        db.flush()

        for line in prepared["lines"]:
            db.add(
                InvoiceLine(
                    invoice_id=invoice.id,
                    position=line["position"],
                    product_id=None,
                    description=line["description"],
                    quantity=line["quantity"],
                    unit=line["unit"],
                    unit_net_price=line["unit_net_price"],
                    vat_rate=line["vat_rate"],
                    discount_type="none",
                    discount_value=0,
                    account_id=account.id,
                    net_total=line["net_total"],
                    vat_total=line["vat_total"],
                    gross_total=line["gross_total"],
                )
            )

        db.add(
            XRechnungDocument(
                invoice_id=invoice.id,
                original_filename=original_filename,
                document_format=parsed["format"],
                sha256=xml_hash,
                xml_content=xml_content,
            )
        )

        db.commit()
        db.refresh(invoice)

    except IntegrityError as exc:
        db.rollback()
        raise XRechnungImportError(
            "Import wegen eines Datenbankkonflikts abgebrochen."
        ) from exc

    except Exception:
        db.rollback()
        raise

    return {
        "invoice_id": invoice.id,
        "status": invoice.status,
        "supplier_reference": invoice.supplier_reference,
        "partner_id": invoice.partner_id,
        "account_id": account.id,
        "net_total": str(invoice.net_total),
        "vat_total": str(invoice.vat_total),
        "gross_total": str(invoice.gross_total),
        "xml_sha256": xml_hash,
        "document_format": parsed["format"],
    }
