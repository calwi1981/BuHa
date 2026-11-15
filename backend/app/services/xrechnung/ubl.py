"""UBL 2.1 invoice parser for BUHA.

Parsing is not equivalent to XRechnung profile validation.
No database writes are performed.
"""

from decimal import Decimal, InvalidOperation
from defusedxml import ElementTree as ET

UBL_INVOICE = (
    "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
)
CAC = (
    "urn:oasis:names:specification:ubl:schema:xsd:"
    "CommonAggregateComponents-2"
)
CBC = (
    "urn:oasis:names:specification:ubl:schema:xsd:"
    "CommonBasicComponents-2"
)

NS = {"cac": CAC, "cbc": CBC}


class UBLParseError(ValueError):
    pass


def value(node, path):
    if node is None:
        return None
    found = node.find(path, NS)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def decimal_value(node, path):
    raw = value(node, path)
    if raw is None:
        return None
    try:
        result = Decimal(raw)
    except InvalidOperation as exc:
        raise UBLParseError(
            f"Ungültiger Dezimalwert: {path}"
        ) from exc
    if not result.is_finite():
        raise UBLParseError(
            f"Nicht endlicher Dezimalwert: {path}"
        )
    return str(result)


def parse_ubl_invoice(xml_bytes: bytes):
    if not xml_bytes:
        raise UBLParseError("XML-Datei ist leer.")

    if len(xml_bytes) > 10 * 1024 * 1024:
        raise UBLParseError("XML-Datei überschreitet 10 MB.")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise UBLParseError(
            "XML-Datei ist syntaktisch ungültig."
        ) from exc

    if root.tag != f"{{{UBL_INVOICE}}}Invoice":
        raise UBLParseError(
            "Keine UBL-2.1-Rechnung."
        )

    supplier = root.find(
        "cac:AccountingSupplierParty/cac:Party", NS
    )
    customer = root.find(
        "cac:AccountingCustomerParty/cac:Party", NS
    )
    totals = root.find(
        "cac:LegalMonetaryTotal", NS
    )

    def party_data(party):
        return {
            "name": (
                value(party, "cac:PartyLegalEntity/cbc:RegistrationName")
                or value(party, "cac:PartyName/cbc:Name")
            ),
            "street": value(
                party, "cac:PostalAddress/cbc:StreetName"
            ),
            "postal_code": value(
                party, "cac:PostalAddress/cbc:PostalZone"
            ),
            "city": value(
                party, "cac:PostalAddress/cbc:CityName"
            ),
            "country": value(
                party,
                "cac:PostalAddress/cac:Country/"
                "cbc:IdentificationCode"
            ),
            "vat_id": value(
                party,
                "cac:PartyTaxScheme/cbc:CompanyID"
            ),
            "endpoint": value(
                party, "cbc:EndpointID"
            ),
        }

    lines = []
    for position, line in enumerate(
        root.findall("cac:InvoiceLine", NS), start=1
    ):
        lines.append({
            "position": position,
            "id": value(line, "cbc:ID"),
            "description": (
                value(line, "cac:Item/cbc:Description")
                or value(line, "cac:Item/cbc:Name")
            ),
            "name": value(
                line, "cac:Item/cbc:Name"
            ),
            "quantity": decimal_value(
                line, "cbc:InvoicedQuantity"
            ),
            "unit_code": (
                line.find("cbc:InvoicedQuantity", NS).get("unitCode")
                if line.find("cbc:InvoicedQuantity", NS) is not None
                else None
            ),
            "unit_net_price": decimal_value(
                line, "cac:Price/cbc:PriceAmount"
            ),
            "net_total": decimal_value(
                line, "cbc:LineExtensionAmount"
            ),
            "vat_rate": decimal_value(
                line,
                "cac:Item/cac:ClassifiedTaxCategory/cbc:Percent"
            ),
            "tax_category": value(
                line,
                "cac:Item/cac:ClassifiedTaxCategory/cbc:ID"
            ),
        })

    result = {
        "format": "UBL",
        "customization_id": value(
            root, "cbc:CustomizationID"
        ),
        "profile_id": value(
            root, "cbc:ProfileID"
        ),
        "invoice_number": value(
            root, "cbc:ID"
        ),
        "invoice_date": value(
            root, "cbc:IssueDate"
        ),
        "due_date": value(
            root, "cbc:DueDate"
        ),
        "invoice_type_code": value(
            root, "cbc:InvoiceTypeCode"
        ),
        "currency": value(
            root, "cbc:DocumentCurrencyCode"
        ),
        "supplier": party_data(supplier),
        "customer": party_data(customer),
        "net_total": decimal_value(
            totals, "cbc:TaxExclusiveAmount"
        ),
        "gross_total": decimal_value(
            totals, "cbc:TaxInclusiveAmount"
        ),
        "tax_total": decimal_value(
            root, "cac:TaxTotal/cbc:TaxAmount"
        ),
        "prepaid_amount": decimal_value(
            totals, "cbc:PrepaidAmount"
        ),
        "payable_amount": decimal_value(
            totals, "cbc:PayableAmount"
        ),
        "lines": lines,
    }

    warnings = []

    if not result["customization_id"]:
        warnings.append(
            "CustomizationID fehlt; XRechnungsprofil nicht nachgewiesen."
        )

    if not result["invoice_number"]:
        warnings.append("Rechnungsnummer fehlt.")

    if not result["invoice_date"]:
        warnings.append("Rechnungsdatum fehlt.")

    if not result["supplier"]["name"]:
        warnings.append("Lieferantenname fehlt.")

    if not lines:
        warnings.append("Keine Rechnungspositionen vorhanden.")

    if result["currency"] != "EUR":
        warnings.append(
            "Währung wird von BUHA derzeit nicht unterstützt."
        )

    result["warnings"] = warnings
    result["validated"] = False
    result["importable"] = False

    return result
