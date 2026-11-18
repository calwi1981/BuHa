"""PDF-Anhaenge fuer Ausgangsrechnungen."""

import hashlib
import re
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select

from app.api.dependencies import TenantUser, DatabaseSession
from app.models.invoice import Invoice
from app.models.invoice_attachment import InvoiceAttachment


router = APIRouter(
    prefix="/api/invoices",
    tags=["Rechnungsanhaenge"],
)

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_TOTAL_SIZE = 20 * 1024 * 1024
MAX_ATTACHMENTS = 20


def attachment_metadata(item):
    return {
        "id": item.id,
        "invoice_id": item.invoice_id,
        "filename": item.filename,
        "mime_type": item.mime_type,
        "file_size": item.file_size,
        "sha256": item.sha256,
        "created_at": item.created_at,
        "locked_at": item.locked_at,
    }


def load_outgoing_invoice(db, invoice_id, tenant_id, lock=False):
    query = select(Invoice).where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)

    if lock:
        query = query.with_for_update()

    invoice = db.execute(query).scalar_one_or_none()

    if invoice is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    if invoice.invoice_type != "outgoing":
        raise HTTPException(
            422,
            "Anhaenge sind nur fuer Ausgangsrechnungen vorgesehen.",
        )

    return invoice


def attachments_locked(db, invoice_id):
    """Sperre bei erfolgreichem oder laufendem E-Mail-Versand."""
    from sqlalchemy import text

    row = db.execute(
        text("""
            SELECT EXISTS (
                SELECT 1
                FROM invoice_email_deliveries
                WHERE invoice_id = :invoice_id
                  AND status IN ('sent', 'pending')
            )
        """),
        {"invoice_id": invoice_id},
    ).scalar_one()

    return bool(row)


@router.get("/{invoice_id}/attachments")
def list_invoice_attachments(
    invoice_id: int,
    db: DatabaseSession,
    user: TenantUser,
):
    load_outgoing_invoice(db, invoice_id, user.tenant_id)

    rows = db.scalars(
        select(InvoiceAttachment)
        .where(InvoiceAttachment.invoice_id == invoice_id)
        .order_by(InvoiceAttachment.id)
    ).all()

    return {
        "locked": attachments_locked(db, invoice_id),
        "attachments": [
            attachment_metadata(item)
            for item in rows
        ],
    }


@router.post("/{invoice_id}/attachments", status_code=201)
async def upload_invoice_attachment(
    invoice_id: int,
    db: DatabaseSession,
    user: TenantUser,
    file: UploadFile = File(...),
):
    invoice = load_outgoing_invoice(db, invoice_id, user.tenant_id, lock=True)

    if attachments_locked(db, invoice.id):
        raise HTTPException(
            409,
            "Anhaenge sind nach erfolgreichem Versand gesperrt.",
        )

    count = db.query(InvoiceAttachment).filter(
        InvoiceAttachment.invoice_id == invoice.id
    ).count()

    if count >= MAX_ATTACHMENTS:
        raise HTTPException(
            422,
            "Maximal 20 Anhaenge pro Rechnung erlaubt.",
        )

    filename = (file.filename or "").strip()
    filename = filename.replace("\\", "/").split("/")[-1]

    if (
        not filename
        or len(filename) > 255
        or not filename.lower().endswith(".pdf")
        or re.search(r"[\x00-\x1f\x7f]", filename)
    ):
        raise HTTPException(
            422,
            "Ungueltiger PDF-Dateiname.",
        )

    content = await file.read(MAX_FILE_SIZE + 1)

    if not content or len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            422,
            "PDF-Datei leer oder groesser als 10 MB.",
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            422,
            "Datei besitzt keinen gueltigen PDF-Header.",
        )

    from sqlalchemy import func

    current_total = db.scalar(
        select(func.coalesce(func.sum(InvoiceAttachment.file_size), 0))
        .where(InvoiceAttachment.invoice_id == invoice.id)
    )

    if int(current_total or 0) + len(content) > MAX_TOTAL_SIZE:
        raise HTTPException(
            422,
            "Maximal 20 MB Gesamtgroesse fuer Rechnungsanhaenge erlaubt.",
        )

    item = InvoiceAttachment(
        invoice_id=invoice.id,
        filename=filename,
        mime_type="application/pdf",
        file_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return attachment_metadata(item)


@router.get("/{invoice_id}/attachments/{attachment_id}")
def download_invoice_attachment(
    invoice_id: int,
    attachment_id: int,
    db: DatabaseSession,
    user: TenantUser,
):
    load_outgoing_invoice(db, invoice_id, user.tenant_id)

    item = db.execute(
        select(InvoiceAttachment)
        .where(InvoiceAttachment.id == attachment_id)
        .where(InvoiceAttachment.invoice_id == invoice_id)
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(404, "Anhang nicht gefunden.")

    return Response(
        content=item.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                "inline; filename=\"rechnung-anhang.pdf\"",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{invoice_id}/attachments/{attachment_id}")
def delete_invoice_attachment(
    invoice_id: int,
    attachment_id: int,
    db: DatabaseSession,
    user: TenantUser,
):
    invoice = load_outgoing_invoice(db, invoice_id, user.tenant_id, lock=True)

    if attachments_locked(db, invoice.id):
        raise HTTPException(
            409,
            "Anhaenge sind nach erfolgreichem Versand gesperrt.",
        )

    item = db.execute(
        select(InvoiceAttachment)
        .where(InvoiceAttachment.id == attachment_id)
        .where(InvoiceAttachment.invoice_id == invoice_id)
    ).scalar_one_or_none()

    if item is None:
        raise HTTPException(404, "Anhang nicht gefunden.")

    db.delete(item)
    db.commit()

    return {"ok": True}
