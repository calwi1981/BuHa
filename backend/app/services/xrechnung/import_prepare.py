"""Prüfung der verlustfreien Übernahme von XRechnungspositionen."""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class XRechnungImportError(ValueError):
    pass


CENT = Decimal("0.01")
PRICE_PRECISION = Decimal("0.0001")
QUANTITY_PRECISION = Decimal("0.001")


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def decimal_field(value, name):
    if value is None or str(value).strip() == "":
        raise XRechnungImportError(f"Pflichtwert fehlt: {name}")

    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise XRechnungImportError(
            f"Ungültiger Dezimalwert: {name}"
        ) from exc

    if not result.is_finite():
        raise XRechnungImportError(
            f"Nicht endlicher Dezimalwert: {name}"
        )

    return result


def prepare_import(parsed):
    if parsed.get("format") not in {"UBL", "CII"}:
        raise XRechnungImportError(
            "Nicht unterstütztes XML-Rechnungsformat."
        )

    if parsed.get("currency") != "EUR":
        raise XRechnungImportError(
            "Der Import unterstützt derzeit ausschließlich EUR."
        )

    if str(parsed.get("invoice_type_code") or "") != "380":
        raise XRechnungImportError(
            "Der Import unterstützt derzeit ausschließlich "
            "reguläre Rechnungen (Typ 380)."
        )

    reference = str(parsed.get("invoice_number") or "").strip()

    if not reference or len(reference) > 100:
        raise XRechnungImportError(
            "Lieferanten-Rechnungsnummer fehlt oder ist zu lang."
        )

    try:
        invoice_date = date.fromisoformat(
            str(parsed.get("invoice_date") or "")
        )
        due_date = (
            date.fromisoformat(str(parsed["due_date"]))
            if parsed.get("due_date")
            else None
        )
    except ValueError as exc:
        raise XRechnungImportError(
            "Ungültiges Rechnungs- oder Fälligkeitsdatum."
        ) from exc

    if due_date is not None and due_date < invoice_date:
        raise XRechnungImportError(
            "Fälligkeitsdatum liegt vor dem Rechnungsdatum."
        )

    source_lines = parsed.get("lines") or []

    if not source_lines:
        raise XRechnungImportError(
            "Die Rechnung enthält keine Positionen."
        )

    prepared_lines = []
    total_net = Decimal("0.00")
    total_vat = Decimal("0.00")

    for position, line in enumerate(source_lines, start=1):
        quantity = decimal_field(
            line.get("quantity"),
            f"Position {position}: Menge",
        )
        unit_price = decimal_field(
            line.get("unit_net_price"),
            f"Position {position}: Einzelpreis",
        )
        source_net = decimal_field(
            line.get("net_total"),
            f"Position {position}: Nettobetrag",
        )
        vat_rate = decimal_field(
            line.get("vat_rate"),
            f"Position {position}: Umsatzsteuersatz",
        )

        if quantity <= 0 or unit_price < 0 or source_net < 0:
            raise XRechnungImportError(
                f"Position {position}: Negative Beträge oder "
                "nicht positive Mengen werden nicht übernommen."
            )

        if vat_rate not in {Decimal("7"), Decimal("19")}:
            raise XRechnungImportError(
                f"Position {position}: Umsatzsteuersatz "
                f"{vat_rate} % wird noch nicht unterstützt."
            )

        if (
            quantity != quantity.quantize(QUANTITY_PRECISION)
            or unit_price != unit_price.quantize(PRICE_PRECISION)
        ):
            raise XRechnungImportError(
                f"Position {position}: Mengen- oder "
                "Preisgenauigkeit überschreitet die BUHA-Feldgrenzen."
            )

        calculated_net = money(quantity * unit_price)

        if calculated_net != money(source_net):
            raise XRechnungImportError(
                f"Position {position}: XML-Nettobetrag "
                f"{money(source_net)} EUR stimmt nicht mit dem "
                f"BUHA-Berechnungswert {calculated_net} EUR überein. "
                "Positionsrabatte oder Preisbasismengen müssen "
                "gesondert behandelt werden."
            )

        description = str(
            line.get("description") or ""
        ).strip()

        if not description:
            raise XRechnungImportError(
                f"Position {position}: Beschreibung fehlt."
            )

        calculated_vat = money(
            calculated_net * vat_rate / Decimal("100")
        )

        prepared_lines.append({
            "position": position,
            "description": description,
            "quantity": quantity,
            "unit": str(line.get("unit") or "Stueck")[:30],
            "unit_net_price": unit_price,
            "vat_rate": vat_rate,
            "net_total": calculated_net,
            "vat_total": calculated_vat,
            "gross_total": money(
                calculated_net + calculated_vat
            ),
        })

        total_net += calculated_net
        total_vat += calculated_vat

    total_net = money(total_net)
    total_vat = money(total_vat)
    total_gross = money(total_net + total_vat)

    xml_net = decimal_field(
        parsed.get("net_total"),
        "Rechnung: Nettogesamtbetrag",
    )
    xml_gross = decimal_field(
        parsed.get("gross_total"),
        "Rechnung: Bruttogesamtbetrag",
    )

    if total_net != money(xml_net):
        raise XRechnungImportError(
            "Der berechnete Nettogesamtbetrag stimmt nicht "
            "mit der XML-Rechnung überein."
        )

    if total_gross != money(xml_gross):
        raise XRechnungImportError(
            "Der berechnete Bruttogesamtbetrag stimmt nicht "
            "mit der XML-Rechnung überein."
        )

    xml_tax = parsed.get("tax_total")

    if xml_tax is None:
        raise XRechnungImportError(
            "Der XML-Gesamtsteuerbetrag fehlt."
        )

    if total_vat != money(decimal_field(
        xml_tax, "Rechnung: Gesamtsteuerbetrag"
    )):
        raise XRechnungImportError(
            "Der XML-Gesamtsteuerbetrag stimmt nicht "
            "mit der BUHA-Berechnung überein."
        )

    prepaid = decimal_field(
        parsed.get("prepaid_amount")
        if parsed.get("prepaid_amount") is not None
        else "0",
        "Rechnung: Vorauszahlungen",
    )

    if prepaid != 0:
        raise XRechnungImportError(
            "Rechnungen mit Vorauszahlungen werden "
            "derzeit nicht automatisch importiert."
        )

    payable = decimal_field(
        parsed.get("payable_amount"),
        "Rechnung: Zahlbetrag",
    )

    if money(payable) != total_gross:
        raise XRechnungImportError(
            "Der XML-Zahlbetrag stimmt nicht "
            "mit dem BUHA-Bruttobetrag überein."
        )

    return {
        "supplier_reference": reference,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "currency": "EUR",
        "lines": prepared_lines,
        "net_total": total_net,
        "vat_total": total_vat,
        "gross_total": total_gross,
    }
