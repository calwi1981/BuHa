"""Central invoice email delivery service for BUHA."""

from datetime import datetime, timezone
from decimal import Decimal

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select, text

from app.api.administration import load_settings, smtp_cipher_buha
from app.models.invoice import Invoice
from app.models.invoice_attachment import InvoiceAttachment
from app.models.invoice_line import InvoiceLine
from app.models.partner import Partner
from app.models.payment import Payment
from app.services.invoice_pdf import render_invoice_pdf
from app.services.smtp_mail import smtp_send_buha


def _amount(value):
    amount = Decimal(str(value))
    return (
        f"{amount:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
        + " EUR"
    )


def _format_date(value):
    return value.strftime("%d.%m.%Y") if value else ""


def _insert_log(db, invoice_id, recipient, subject, delivery_type):
    return db.execute(
        text("""
            INSERT INTO invoice_email_deliveries
                (invoice_id, recipient, subject, delivery_type, status)
            VALUES
                (:invoice_id, :recipient, :subject, :delivery_type,
                 'pending')
            RETURNING id
        """),
        {
            "invoice_id": invoice_id,
            "recipient": recipient,
            "subject": subject[:500],
            "delivery_type": delivery_type,
        },
    ).scalar_one()


def _finish_log(db, log_id, status, error=None):
    db.execute(
        text("""
            UPDATE invoice_email_deliveries
            SET status=:status,
                error_message=:error,
                completed_at=now()
            WHERE id=:log_id
        """),
        {
            "log_id": log_id,
            "status": status,
            "error": error[:1000] if error else None,
        },
    )
    db.commit()


def deliver_invoice_email(db, invoice_id, tenant_id: int, delivery_type="manual", force_xrechnung=False):
    """Send a finalized outgoing invoice and persist delivery status.

    Returns a result dictionary. SMTP errors do not undo invoice
    finalization. The SMTP server accepting a message is not proof
    of final delivery to the recipient.
    """
    if delivery_type not in {"manual", "automatic"}:
        raise ValueError("Ungültige Versandart.")

    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise ValueError("Gueltige Mandanten-ID erforderlich.")

    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id,
        )
    )

    if invoice is None:
        raise ValueError("Rechnung nicht gefunden.")

    if invoice.invoice_type != "outgoing":
        raise ValueError("Nur Ausgangsrechnungen können versendet werden.")

    if invoice.status == "draft":
        raise ValueError("Rechnungsentwurf ist nicht freigegeben.")

    partner = db.scalar(
        select(Partner).where(
            Partner.id == invoice.partner_id,
            Partner.tenant_id == tenant_id,
        )
    )
    if partner is None:
        raise ValueError("Geschaeftspartner nicht gefunden.")

    settings = load_settings(db, tenant_id)

    recipient = str(
        getattr(partner, "email", None) or ""
    ).strip()

    subject = str(
        settings.get("invoice_mail_subject")
        or "Ihre Rechnung {rechnungsnummer}"
    )
    body = str(
        settings.get("invoice_mail_body")
        or "Anbei erhalten Sie unsere Rechnung {rechnungsnummer}."
    )

    replacements = {
        "{rechnungsnummer}": str(invoice.invoice_number),
        "{rechnungsdatum}": _format_date(invoice.invoice_date),
        "{faelligkeit}": _format_date(invoice.due_date),
        "{kundenname}": str(getattr(partner, "name", "") or ""),
        "{bruttobetrag}": _amount(invoice.gross_total),
        "{firmenname}": str(settings.get("company_name") or ""),
    }

    for key, value in replacements.items():
        subject = subject.replace(key, value)
        body = body.replace(key, value)

    # Gespeicherte Escape-Sequenzen in echte Zeilenumbrueche umwandeln.
    body = (
        body.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
    )

    # Dieselbe Rechnungssperre wie beim Anhang-Upload verwenden.
    # Dadurch kann zwischen Sperrpruefung und pending-Protokoll
    # kein Dokument hinzugefuegt oder geloescht werden.
    db.execute(
        select(Invoice.id)
        .where(
            Invoice.id == invoice.id,
            Invoice.tenant_id == tenant_id,
        )
        .with_for_update()
    ).scalar_one()

    log_id = _insert_log(
        db,
        invoice.id,
        recipient,
        subject,
        delivery_type,
    )
    db.commit()

    try:
        if not recipient:
            raise ValueError(
                "Beim Kunden ist keine E-Mail-Adresse hinterlegt."
            )

        recipient = validate_email(
            recipient,
            check_deliverability=False,
        ).normalized

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

        row = db.execute(
            text(
                "SELECT logo FROM company_settings "
                "WHERE tenant_id=:tenant_id"
            ),
            {"tenant_id": tenant_id},
        ).first()

        logo = bytes(row[0]) if row and row[0] else None

        from app.models.product import Product

        for pdf_line in lines:
            if pdf_line.product_id is not None:
                pdf_product = db.get(Product, pdf_line.product_id)
                if pdf_product is not None:
                    pdf_line._pdf_product_label = (
                        f'{pdf_product.sku} - {pdf_product.name}'
                    )

        pdf = render_invoice_pdf(
            invoice,
            partner,
            lines,
            payments,
            settings,
            logo,
        )

        stored_attachments = db.scalars(
            select(InvoiceAttachment)
            .where(InvoiceAttachment.invoice_id == invoice.id)
            .order_by(InvoiceAttachment.id)
        ).all()

        extra_attachments = [
            {
                "content": bytes(item.content),
                "filename": item.filename,
                "subtype": "pdf",
            }
            for item in stored_attachments
        ]

        if force_xrechnung or getattr(invoice, "xrechnung_enabled", False):
            from app.services.xrechnung.ubl_export import (
                generate_ubl_invoice,
            )
            from app.services.xrechnung.validator import (
                validate_xrechnung,
            )

            xml = generate_ubl_invoice(
                invoice,
                partner,
                lines,
                settings,
            )

            validate_xrechnung(xml)

            extra_attachments.append({
                "content": xml,
                "filename": f"{invoice.invoice_number}.xml",
                "subtype": "xml",
            })

        smtp_send_buha(
            settings=settings,
            cipher=smtp_cipher_buha(),
            recipient=recipient,
            subject=subject,
            body=body,
            attachment=pdf,
            filename=f"{invoice.invoice_number}.pdf",
            extra_attachments=extra_attachments,
        )

        _finish_log(db, log_id, "sent")

        return {
            "ok": True,
            "status": "sent",
            "recipient": recipient,
            "delivery_id": log_id,
        }

    except Exception as error:
        db.rollback()

        from app.services.xrechnung.ubl_export import UBLExportError
        from app.services.xrechnung.validator import XRechnungValidationError

        if isinstance(error, (UBLExportError, XRechnungValidationError)):
            message = str(error)
        elif isinstance(error, ValueError):
            message = str(error)
        else:
            message = (
                "Rechnungsversand fehlgeschlagen. "
                "SMTP-Konfiguration oder Rechnungsdaten prüfen."
            )

        _finish_log(db, log_id, "failed", message)

        return {
            "ok": False,
            "status": "failed",
            "recipient": recipient,
            "delivery_id": log_id,
            "error": message,
        }


def invoice_email_history(db, invoice_id, tenant_id: int):
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise ValueError("Gueltige Mandanten-ID erforderlich.")

    rows = db.execute(
        text("""
            SELECT d.id, d.recipient, d.subject, d.delivery_type,
                   d.status, d.error_message,
                   d.created_at, d.completed_at
            FROM invoice_email_deliveries AS d
            JOIN invoices AS i ON i.id = d.invoice_id
            WHERE d.invoice_id = :invoice_id
              AND i.tenant_id = :tenant_id
            ORDER BY d.created_at DESC, d.id DESC
        """),
        {
            "invoice_id": invoice_id,
            "tenant_id": tenant_id,
        },
    ).mappings().all()

    return [dict(row) for row in rows]
