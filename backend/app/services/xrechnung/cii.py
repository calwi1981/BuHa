"""CII Cross Industry Invoice parser for BUHA.

Parsing is not equivalent to XRechnung profile validation.
No database writes are performed.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as ET


RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

NS = {"rsm": RSM, "ram": RAM, "udt": UDT}


class CIIParseError(ValueError):
    pass


def value(node, path):
    if node is None:
        return None
    element = node.find(path, NS)
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def decimal_value(node, path):
    raw = value(node, path)
    if raw is None:
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise CIIParseError(
            f"Ungültiger Dezimalwert: {path}"
        ) from exc

    if not number.is_finite():
        raise CIIParseError(
            f"Nicht endlicher Dezimalwert: {path}"
        )

    return str(number)


def date_value(node, path):
    raw = value(node, path)
    if not raw:
        return None

    if len(raw) != 8 or not raw.isdigit():
        raise CIIParseError("Ungültiges CII-Datumsformat.")

    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError as exc:
        raise CIIParseError("Ungültiges CII-Datum.") from exc


def party_data(party):
    tax_id = None

    if party is not None:
        for registration in party.findall(
            "ram:SpecifiedTaxRegistration", NS
        ):
            element = registration.find("ram:ID", NS)
            if element is not None and element.get("schemeID") == "VA":
                tax_id = (element.text or "").strip() or None
                break

    address = (
        party.find("ram:PostalTradeAddress", NS)
        if party is not None else None
    )

    endpoint = None
    endpoint_scheme = None

    if party is not None:
        uri = party.find("ram:URIUniversalCommunication/ram:URIID", NS)
        if uri is not None:
            endpoint = (uri.text or "").strip() or None
            endpoint_scheme = uri.get("schemeID")

    return {
        "name": value(party, "ram:Name"),
        "street": value(address, "ram:LineOne"),
        "postal_code": value(address, "ram:PostcodeCode"),
        "city": value(address, "ram:CityName"),
        "country": value(address, "ram:CountryID"),
        "vat_id": tax_id,
        "endpoint": endpoint,
        "endpoint_scheme": endpoint_scheme,
    }


def parse_cii_invoice(xml_bytes: bytes):
    if not xml_bytes:
        raise CIIParseError("XML-Datei ist leer.")

    if len(xml_bytes) > 10 * 1024 * 1024:
        raise CIIParseError("XML-Datei überschreitet 10 MB.")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise CIIParseError(
            "XML-Datei ist syntaktisch ungültig."
        ) from exc

    if root.tag != f"{{{RSM}}}CrossIndustryInvoice":
        raise CIIParseError("Keine CII-Rechnung.")

    context = root.find(
        "rsm:ExchangedDocumentContext", NS
    )
    document = root.find(
        "rsm:ExchangedDocument", NS
    )
    transaction = root.find(
        "rsm:SupplyChainTradeTransaction", NS
    )

    if document is None or transaction is None:
        raise CIIParseError(
            "CII-Rechnungsstruktur ist unvollständig."
        )

    agreement = transaction.find(
        "ram:ApplicableHeaderTradeAgreement", NS
    )
    settlement = transaction.find(
        "ram:ApplicableHeaderTradeSettlement", NS
    )

    supplier = (
        agreement.find("ram:SellerTradeParty", NS)
        if agreement is not None else None
    )
    customer = (
        agreement.find("ram:BuyerTradeParty", NS)
        if agreement is not None else None
    )

    totals = (
        settlement.find(
            "ram:SpecifiedTradeSettlementHeaderMonetarySummation",
            NS,
        )
        if settlement is not None else None
    )

    lines = []

    for position, line in enumerate(
        transaction.findall(
            "ram:IncludedSupplyChainTradeLineItem", NS
        ),
        start=1,
    ):
        line_document = line.find(
            "ram:AssociatedDocumentLineDocument", NS
        )
        product = line.find(
            "ram:SpecifiedTradeProduct", NS
        )
        agreement_line = line.find(
            "ram:SpecifiedLineTradeAgreement", NS
        )
        delivery_line = line.find(
            "ram:SpecifiedLineTradeDelivery", NS
        )
        settlement_line = line.find(
            "ram:SpecifiedLineTradeSettlement", NS
        )

        quantity_node = (
            delivery_line.find("ram:BilledQuantity", NS)
            if delivery_line is not None else None
        )

        tax = (
            settlement_line.find("ram:ApplicableTradeTax", NS)
            if settlement_line is not None else None
        )

        lines.append({
            "position": position,
            "id": value(line_document, "ram:LineID"),
            "description": (
                value(product, "ram:Description")
                or value(product, "ram:Name")
            ),
            "name": value(product, "ram:Name"),
            "quantity": decimal_value(
                delivery_line, "ram:BilledQuantity"
            ),
            "unit_code": (
                quantity_node.get("unitCode")
                if quantity_node is not None else None
            ),
            "unit_net_price": decimal_value(
                agreement_line,
                "ram:NetPriceProductTradePrice/ram:ChargeAmount",
            ),
            "net_total": decimal_value(
                settlement_line,
                "ram:SpecifiedTradeSettlementLineMonetarySummation/"
                "ram:LineTotalAmount",
            ),
            "vat_rate": decimal_value(
                tax, "ram:RateApplicablePercent"
            ),
            "tax_category": value(
                tax, "ram:CategoryCode"
            ),
        })

    result = {
        "format": "CII",
        "customization_id": value(
            context,
            "ram:GuidelineSpecifiedDocumentContextParameter/"
            "ram:ID",
        ),
        "profile_id": None,
        "invoice_number": value(document, "ram:ID"),
        "invoice_date": date_value(
            document,
            "ram:IssueDateTime/udt:DateTimeString",
        ),
        "due_date": date_value(
            settlement,
            "ram:SpecifiedTradePaymentTerms/"
            "ram:DueDateDateTime/udt:DateTimeString",
        ),
        "invoice_type_code": value(
            document, "ram:TypeCode"
        ),
        "currency": value(
            settlement, "ram:InvoiceCurrencyCode"
        ),
        "supplier": party_data(supplier),
        "customer": party_data(customer),
        "net_total": decimal_value(
            totals, "ram:TaxBasisTotalAmount"
        ),
        "gross_total": decimal_value(
            totals, "ram:GrandTotalAmount"
        ),
        "tax_total": decimal_value(
            totals, "ram:TaxTotalAmount"
        ),
        "prepaid_amount": decimal_value(
            totals, "ram:TotalPrepaidAmount"
        ),
        "payable_amount": decimal_value(
            totals, "ram:DuePayableAmount"
        ),
        "lines": lines,
    }

    warnings = []

    if not result["customization_id"]:
        warnings.append("XRechnungsprofil nicht nachgewiesen.")

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
