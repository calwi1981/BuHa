"""Prüfungen vor dem Import elektronischer Eingangsrechnungen."""

from sqlalchemy import select

from app.models.partner import Partner
from app.models.invoice import Invoice


def normalize(value):
    return " ".join(str(value or "").casefold().split())


def normalize_vat_id(value):
    return "".join(
        char for char in str(value or "").upper()
        if char.isalnum()
    )


def match_supplier(db, supplier_data, tenant_id):
    """Lieferanten anhand USt-ID oder Name und Anschrift zuordnen."""

    suppliers = db.scalars(
        select(Partner).where(
            Partner.tenant_id == tenant_id,
            Partner.is_supplier.is_(True),
            Partner.is_active.is_(True),
        )
    ).all()

    incoming_vat = normalize_vat_id(
        supplier_data.get("vat_id")
    )

    if incoming_vat:
        vat_matches = [
            partner for partner in suppliers
            if normalize_vat_id(partner.vat_id) == incoming_vat
        ]

        if len(vat_matches) == 1:
            return {
                "status": "matched",
                "method": "vat_id",
                "partner_id": vat_matches[0].id,
                "partner_name": vat_matches[0].name,
            }

        if len(vat_matches) > 1:
            return {
                "status": "ambiguous",
                "method": "vat_id",
                "partner_id": None,
                "partner_name": None,
            }

    fields = ("name", "street", "postal_code", "city", "country")

    if not all(
        normalize(supplier_data.get(field))
        for field in fields
    ):
        return {
            "status": "not_found",
            "method": None,
            "partner_id": None,
            "partner_name": None,
        }

    address_matches = [
        partner for partner in suppliers
        if all(
            normalize(getattr(partner, field, None))
            == normalize(supplier_data.get(field))
            for field in fields
        )
    ]

    if len(address_matches) == 1:
        partner = address_matches[0]
        return {
            "status": "matched",
            "method": "name_address",
            "partner_id": partner.id,
            "partner_name": partner.name,
        }

    return {
        "status": (
            "ambiguous" if len(address_matches) > 1
            else "not_found"
        ),
        "method": "name_address",
        "partner_id": None,
        "partner_name": None,
    }


def check_duplicate(db, partner_id, supplier_reference, tenant_id):
    """Doppelte Eingangsrechnungen desselben Lieferanten erkennen."""

    if not partner_id or not str(supplier_reference or "").strip():
        return {
            "duplicate": False,
            "invoice_id": None,
            "reason": "Prüfung mangels Zuordnung oder Nummer nicht möglich",
        }

    reference = str(supplier_reference).strip()

    existing = db.scalars(
        select(Invoice).where(
            Invoice.tenant_id == tenant_id,
            Invoice.invoice_type == "incoming",
            Invoice.partner_id == partner_id,
            Invoice.supplier_reference == reference,
        )
    ).first()

    return {
        "duplicate": existing is not None,
        "invoice_id": existing.id if existing else None,
        "reason": (
            "Eingangsrechnung bereits vorhanden"
            if existing else None
        ),
    }


def select_supplier(db, partner_id, supplier_reference, tenant_id):
    """Manuell ausgewählten Lieferanten prüfen und Dubletten suchen."""

    try:
        partner_id = int(partner_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Ungültige Lieferanten-ID.") from exc

    partner = db.scalar(select(Partner).where(Partner.id == partner_id, Partner.tenant_id == tenant_id))

    if partner is None:
        raise ValueError("Lieferant nicht gefunden.")

    if not partner.is_supplier:
        raise ValueError(
            "Der ausgewählte Geschäftspartner ist kein Lieferant."
        )

    if not partner.is_active:
        raise ValueError(
            "Der ausgewählte Lieferant ist deaktiviert."
        )

    duplicate = check_duplicate(
        db,
        partner.id,
        supplier_reference,
        tenant_id,
    )

    return {
        "status": "matched",
        "method": "manual",
        "partner_id": partner.id,
        "partner_name": partner.name,
        "duplicate_check": duplicate,
    }
