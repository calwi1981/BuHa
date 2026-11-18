"""Mandantenbezogene Nummernvergabe für direkte Geldbuchungen."""

from fastapi import HTTPException
from sqlalchemy import text


def next_manual_booking_number(db, tenant_id, booking_type, booking_date):
    if booking_type not in ("income", "expense"):
        raise HTTPException(422, "Ungültige Buchungsart.")

    # Dieselbe Transaktionssperre wie bei der Rechnungsnummernvergabe.
    db.execute(text("SELECT pg_advisory_xact_lock(127001)"))

    settings = db.execute(
        text(
            "SELECT settings FROM company_settings "
            "WHERE tenant_id=:tenant_id"
        ),
        {"tenant_id": tenant_id},
    ).scalar_one_or_none()

    if settings is None:
        raise HTTPException(422, "Mandanteneinstellungen fehlen.")

    key = "booking_income" if booking_type == "income" else "booking_expense"

    default_prefix = "E" if booking_type == "income" else "A"
    prefix = settings.get(key + "_prefix", default_prefix)
    digits = int(settings.get(key + "_digits", 4))
    minimum = int(settings.get(key + "_next", 1))

    if (
        not isinstance(prefix, str)
        or not prefix.isalpha()
        or not 1 <= len(prefix) <= 8
        or not 3 <= digits <= 8
        or minimum < 1
    ):
        raise HTTPException(422, "Ungültige Buchungsnummern-Einstellungen.")

    year = booking_date.year
    kind = "booking_" + booking_type
    stem = f"{prefix}-{year}-"

    row = db.execute(
        text("""
            SELECT last_number
            FROM invoice_sequences
            WHERE tenant_id=:tenant_id
              AND invoice_type=:kind
              AND year=:year
            FOR UPDATE
        """),
        {"tenant_id": tenant_id, "kind": kind, "year": year},
    ).first()

    candidate = max((row[0] if row else 0) + 1, minimum)

    while True:
        number = stem + str(candidate).zfill(digits)

        occupied = db.execute(
            text("""
                SELECT 1
                FROM manual_bookings
                WHERE tenant_id=:tenant_id
                  AND booking_number=:number
                UNION ALL
                SELECT 1
                FROM invoices
                WHERE tenant_id=:tenant_id
                  AND invoice_number=:number
                LIMIT 1
            """),
            {"tenant_id": tenant_id, "number": number},
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
            "tenant_id": tenant_id,
            "kind": kind,
            "year": year,
            "number": candidate,
        },
    )

    return number
