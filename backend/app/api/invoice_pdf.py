from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, text

from app.api.dependencies import DatabaseSession, TenantUser
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.partner import Partner
from app.models.payment import Payment
from app.services.invoice_pdf import render_invoice_pdf

router = APIRouter(prefix="/api/invoices", tags=["Rechnungs-PDF"])


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: int,
    db: DatabaseSession,
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

    if invoice.invoice_type != "outgoing":
        raise HTTPException(422, "Nur Ausgangsrechnungen.")

    if invoice.status == "draft":
        raise HTTPException(409, "Entwurf nicht freigegeben.")

    partner = db.scalar(
        select(Partner).where(
            Partner.id == invoice.partner_id,
            Partner.tenant_id == tenant.tenant_id,
        )
    )
    if partner is None:
        raise HTTPException(404, "Geschaeftspartner nicht gefunden.")

    lines = db.scalars(
        select(InvoiceLine)
        .where(InvoiceLine.invoice_id == invoice_id)
        .order_by(InvoiceLine.position)
    ).all()

    payments = db.scalars(
        select(Payment)
        .where(Payment.invoice_id == invoice_id)
        .order_by(Payment.payment_date, Payment.id)
    ).all()

    row = db.execute(
        text("""
            SELECT logo
            FROM company_settings
            WHERE tenant_id=:tenant_id
        """),
        {"tenant_id": tenant.tenant_id},
    ).first()

    settings = load_settings(db, tenant.tenant_id)
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
        invoice, partner, lines, payments, settings, logo
    )

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{invoice.invoice_number}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff"
        }
    )


from app.services.smtp_mail import smtp_send_buha
from app.api.administration import load_settings, smtp_cipher_buha


@router.post("/{invoice_id}/send-email")
def send_invoice_email_buha(
    invoice_id: int,
    db: DatabaseSession,
    tenant: TenantUser,
):
    from app.services.invoice_email import deliver_invoice_email

    result = deliver_invoice_email(
        db,
        invoice_id,
        tenant_id=tenant.tenant_id,
        delivery_type="manual",
    )

    if not result["ok"]:
        raise HTTPException(
            502,
            result.get("error") or "E-Mail-Versand fehlgeschlagen.",
        )

    return result


@router.get("/{invoice_id}/email-history")
def get_invoice_email_history(
    invoice_id: int,
    db: DatabaseSession,
    tenant: TenantUser,
):
    from app.services.invoice_email import invoice_email_history

    invoice = db.scalar(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant.tenant_id,
        )
    )

    if invoice is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    return invoice_email_history(db, invoice_id, tenant.tenant_id)
