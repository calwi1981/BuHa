"""Berechnung von Nebenkosten auf Basis bestehender Ausgangsrechnungen."""

from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")


def amount(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_utility_statement(items, prepayments):
    """Berechnet Kostenanteile, Vorauszahlungen und Abrechnungsergebnis."""

    if not isinstance(items, list):
        raise ValueError("Betriebskostenpositionen müssen eine Liste sein.")

    advance = amount(prepayments)

    if advance < 0:
        raise ValueError("Vorauszahlungen dürfen nicht negativ sein.")

    positions = []
    total = Decimal("0.00")

    for index, item in enumerate(items, 1):
        total_cost = amount(item["total_cost"])
        total_key = Decimal(str(item["total_key"]))
        tenant_key = Decimal(str(item["tenant_key"]))

        if total_cost < 0:
            raise ValueError(
                f"Position {index}: Gesamtkosten dürfen nicht negativ sein."
            )

        if total_key <= 0:
            raise ValueError(
                f"Position {index}: Gesamtschlüssel muss größer null sein."
            )

        if tenant_key < 0 or tenant_key > total_key:
            raise ValueError(
                f"Position {index}: Mieterschlüssel ist ungültig."
            )

        share = (
            total_cost * tenant_key / total_key
        ).quantize(CENT, rounding=ROUND_HALF_UP)

        total += share

        positions.append({
            "description": str(item.get("description", "")),
            "total_cost": total_cost,
            "total_key": total_key,
            "tenant_key": tenant_key,
            "tenant_share": share,
        })

    difference = (total - advance).quantize(
        CENT, rounding=ROUND_HALF_UP
    )

    return {
        "positions": positions,
        "total_tenant_cost": total,
        "prepayments": advance,
        "difference": difference,
        "additional_payment": max(difference, Decimal("0.00")),
        "credit": max(-difference, Decimal("0.00")),
    }
