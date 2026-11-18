"""XRechnung-Import: isolierter Integrationstest ohne dauerhafte Daten."""

import hashlib
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.account import Account
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.partner import Partner
from app.models.tenant import Tenant
from app.models.xrechnung_document import XRechnungDocument
from app.services.xrechnung.import_prepare import XRechnungImportError
from app.services.xrechnung.import_save import save_incoming_xrechnung


def run():
    reference = "XR-TEST-" + uuid4().hex[:16]
    xml_content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<IntegrationTest reference="' + reference + '"/>'
    ).encode("utf-8")

    parsed = {
        "format": "UBL",
        "invoice_type_code": "380",
        "invoice_number": reference,
        "invoice_date": "2026-11-14",
        "due_date": "2026-11-28",
        "currency": "EUR",
        "net_total": "100.00",
        "tax_total": "19.00",
        "gross_total": "119.00",
        "payable_amount": "119.00",
        "prepaid_amount": "0.00",
        "lines": [{
            "description": "Integrationstest",
            "quantity": "2.000",
            "unit_net_price": "50.0000",
            "net_total": "100.00",
            "vat_rate": "19",
            "unit": "Stueck",
        }],
    }

    with engine.connect() as connection:
        outer = connection.begin()

        try:
            with Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as db:

                tenant = db.scalar(
                    select(Tenant).where(Tenant.code == "calwi.de")
                )
                if tenant is None:
                    raise RuntimeError("Testmandant calwi.de fehlt.")

                partner = db.scalar(
                    select(Partner)
                    .where(
                        Partner.tenant_id == tenant.id,
                        Partner.is_active.is_(True),
                        Partner.is_supplier.is_(True),
                    )
                    .order_by(Partner.id)
                )

                account = db.scalar(
                    select(Account)
                    .where(
                        Account.tenant_id == tenant.id,
                        Account.is_active.is_(True),
                        Account.account_type == "expense",
                    )
                    .order_by(Account.id)
                )

                if partner is None or account is None:
                    raise RuntimeError(
                        "Aktiver Lieferant oder aktives Aufwandskonto fehlt."
                    )

                print("TEST-LIEFERANT:", partner.id)
                print("TEST-AUFWANDSKONTO:", account.number)

                result = save_incoming_xrechnung(
                    db,
                    parsed=parsed,
                    xml_content=xml_content,
                    original_filename="integrationstest.xml",
                    partner_id=partner.id,
                    account_id=account.id,
                    tenant_id=tenant.id,
                )

                invoice_id = result["invoice_id"]

                invoice = db.get(Invoice, invoice_id)
                assert invoice is not None
                assert invoice.tenant_id == tenant.id
                assert invoice.invoice_type == "incoming"
                assert invoice.status == "draft"
                assert invoice.supplier_reference == reference
                assert invoice.gross_total == Decimal("119.00")
                print("OK: Eingangsrechnung als Entwurf angelegt")

                lines = db.scalars(
                    select(InvoiceLine)
                    .where(InvoiceLine.invoice_id == invoice_id)
                ).all()

                assert len(lines) == 1
                assert lines[0].account_id == account.id
                assert lines[0].vat_total == Decimal("19.00")
                print("OK: Rechnungsposition und Aufwandskonto")

                document = db.scalar(
                    select(XRechnungDocument)
                    .where(XRechnungDocument.invoice_id == invoice_id)
                )

                assert document is not None
                assert document.xml_content == xml_content
                assert document.sha256 == hashlib.sha256(
                    xml_content
                ).hexdigest()
                print("OK: Original-XML und SHA256 archiviert")

                try:
                    save_incoming_xrechnung(
                        db,
                        parsed=parsed,
                        xml_content=xml_content,
                        original_filename="integrationstest.xml",
                        partner_id=partner.id,
                        account_id=account.id,
                    tenant_id=tenant.id,
                    )
                except XRechnungImportError:
                    print("OK: Doppelimport abgelehnt")
                else:
                    raise AssertionError(
                        "Doppelimport wurde nicht verhindert."
                    )

                # Auch nach dem erwarteten Fehler darf die äußere
                # Transaktion nicht abgeschlossen worden sein.
                assert outer.is_active
                print("OK: Äußere Testtransaktion weiterhin aktiv")

        finally:
            if outer.is_active:
                outer.rollback()
                print("OK: Äußere Transaktion zurückgerollt")

    # Kontrolle über eine neue Datenbankverbindung.
    with Session(engine) as check:
        remaining = check.scalar(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.supplier_reference == reference)
        )

        archived = check.scalar(
            select(func.count())
            .select_from(XRechnungDocument)
            .where(
                XRechnungDocument.sha256 ==
                hashlib.sha256(xml_content).hexdigest()
            )
        )

        assert remaining == 0
        assert archived == 0

    print("OK: Keine Testrechnung verblieben")
    print("OK: Kein Test-XML verblieben")
    print("ERGEBNIS: INTEGRATIONSTEST BESTANDEN")


if __name__ == "__main__":
    run()
