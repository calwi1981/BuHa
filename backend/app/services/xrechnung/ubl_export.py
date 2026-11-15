"""UBL 2.1 XML generation for BUHA outgoing invoices.

Technical XML generation only. Successful generation does not
establish XRechnung conformance. A separate EN16931/XRechnung
validator is required before sending.
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

UBL = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
CAC = (
    "urn:oasis:names:specification:ubl:schema:xsd:"
    "CommonAggregateComponents-2"
)
CBC = (
    "urn:oasis:names:specification:ubl:schema:xsd:"
    "CommonBasicComponents-2"
)

ET.register_namespace("", UBL)
ET.register_namespace("cac", CAC)
ET.register_namespace("cbc", CBC)


class UBLExportError(ValueError):
    pass


def add(parent, namespace, name, value=None, **attributes):
    element = ET.SubElement(
        parent, f"{{{namespace}}}{name}", attributes
    )
    if value is not None:
        element.text = str(value)
    return element


def amount(value):
    rounded = Decimal(str(value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return f"{rounded:.2f}"


def require(value, label):
    if value is None or not str(value).strip():
        raise UBLExportError(f"Pflichtangabe fehlt: {label}")
    return str(value).strip()


def party(parent, data, customer=False):
    p = add(parent, CAC, "Party")

    endpoint = data.get("endpoint")
    scheme = data.get("endpoint_scheme")

    require(endpoint, "Elektronische Adresse")
    require(scheme, "Adressschema")
    add(p, CBC, "EndpointID", endpoint, schemeID=scheme)

    name = add(p, CAC, "PartyName")
    add(
        name, CBC, "Name",
        require(data.get("name"), "Name")
    )

    address = add(p, CAC, "PostalAddress")
    add(
        address, CBC, "StreetName",
        require(data.get("street"), "Straße")
    )
    add(
        address, CBC, "CityName",
        require(data.get("city"), "Ort")
    )
    add(
        address, CBC, "PostalZone",
        require(data.get("postal_code"), "Postleitzahl")
    )

    country = add(address, CAC, "Country")
    add(
        country, CBC, "IdentificationCode",
        require(data.get("country"), "Land")
    )

    vat_id = data.get("vat_id")
    if vat_id:
        tax = add(p, CAC, "PartyTaxScheme")
        add(tax, CBC, "CompanyID", vat_id)
        scheme = add(tax, CAC, "TaxScheme")
        add(scheme, CBC, "ID", "VAT")

    legal = add(p, CAC, "PartyLegalEntity")
    add(legal, CBC, "RegistrationName", data["name"])

    if not customer:
        contact = add(p, CAC, "Contact")
        add(
            contact, CBC, "Name",
            require(data.get("contact_name"), "Ansprechpartner Rechnungssteller")
        )
        add(
            contact, CBC, "Telephone",
            require(data.get("phone"), "Telefonnummer Rechnungssteller")
        )
        email = data.get("email")
        if email:
            add(contact, CBC, "ElectronicMail", email)


def generate_ubl_invoice(invoice, partner, lines, settings):
    if invoice.invoice_type != "outgoing":
        raise UBLExportError("Nur Ausgangsrechnungen.")

    if invoice.status == "draft":
        raise UBLExportError("Entwurf ist nicht freigegeben.")

    if invoice.currency != "EUR":
        raise UBLExportError("Nur EUR wird unterstützt.")

    if not lines:
        raise UBLExportError("Rechnungspositionen fehlen.")

    seller = {
        "contact_name": settings.get("company_name"),
        "phone": settings.get("phone"),
        "name": settings.get("company_name"),
        "street": settings.get("street"),
        "postal_code": settings.get("postal_code"),
        "city": settings.get("city"),
        "country": settings.get("country") or "DE",
        "vat_id": settings.get("vat_id"),
        "email": settings.get("email"),
        "endpoint": (
            settings.get("xrechnung_endpoint")
            or settings.get("email")
        ),
        "endpoint_scheme": (
            settings.get("xrechnung_endpoint_scheme")
            or ("EM" if settings.get("email") else None)
        ),
    }

    buyer = {
        "name": partner.name,
        "street": partner.street,
        "postal_code": partner.postal_code,
        "city": partner.city,
        "country": partner.country,
        "vat_id": partner.vat_id,
        "endpoint": (
            getattr(partner, "xrechnung_endpoint", None)
            or (
                getattr(partner, "email", None)
                if (
                    getattr(partner, "xrechnung_endpoint_scheme", None)
                    or "EM"
                ).upper() == "EM"
                else None
            )
        ),
        "endpoint_scheme": (
            getattr(partner, "xrechnung_endpoint_scheme", None)
            or ("EM" if getattr(partner, "email", None) else None)
        ),
    }

    root = ET.Element(f"{{{UBL}}}Invoice")

    add(root, CBC, "UBLVersionID", "2.1")

    add(
        root, CBC, "CustomizationID",
        "urn:cen.eu:en16931:2017#compliant#"
        "urn:xeinkauf.de:kosit:xrechnung_3.0"
    )
    add(
        root, CBC, "ProfileID",
        "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
    )

    add(
        root, CBC, "ID",
        require(invoice.invoice_number, "Rechnungsnummer")
    )
    add(
        root, CBC, "IssueDate",
        invoice.invoice_date.isoformat()
    )
    if invoice.due_date:
        add(
            root, CBC, "DueDate",
            invoice.due_date.isoformat()
        )

    add(root, CBC, "InvoiceTypeCode", "380")
    add(root, CBC, "DocumentCurrencyCode", "EUR")

    buyer_reference = (
        getattr(invoice, "xrechnung_buyer_reference", None)
        or getattr(partner, "xrechnung_buyer_reference", None)
    )
    add(
        root, CBC, "BuyerReference",
        require(buyer_reference, "Kaeuferreferenz / Leitweg-ID")
    )

    supplier = add(root, CAC, "AccountingSupplierParty")
    party(supplier, seller)

    customer = add(root, CAC, "AccountingCustomerParty")
    party(customer, buyer, customer=True)

    if settings.get("iban"):
        payment = add(root, CAC, "PaymentMeans")
        add(payment, CBC, "PaymentMeansCode", "58")
        account = add(payment, CAC, "PayeeFinancialAccount")
        add(account, CBC, "ID", settings["iban"])
        if settings.get("bank_holder"):
            add(
                account, CBC, "Name",
                settings["bank_holder"]
            )
        if settings.get("bic"):
            branch = add(account, CAC, "FinancialInstitutionBranch")
            add(branch, CBC, "ID", settings["bic"])

    tax_groups = defaultdict(
        lambda: [Decimal("0"), Decimal("0")]
    )

    for line in lines:
        rate = Decimal(str(line.vat_rate))
        if rate not in {Decimal("7"), Decimal("19")}:
            raise UBLExportError(
                "XRechnung: Der Steuersatz "
                f"{rate} Prozent wird noch nicht unterstuetzt."
            )
        tax_groups[rate][0] += Decimal(str(line.net_total))
        tax_groups[rate][1] += Decimal(str(line.vat_total))

    tax_total = add(root, CAC, "TaxTotal")
    add(
        tax_total, CBC, "TaxAmount",
        amount(invoice.vat_total),
        currencyID="EUR"
    )

    for rate, (net, tax) in sorted(tax_groups.items()):
        subtotal = add(tax_total, CAC, "TaxSubtotal")
        add(
            subtotal, CBC, "TaxableAmount",
            amount(net), currencyID="EUR"
        )
        add(
            subtotal, CBC, "TaxAmount",
            amount(tax), currencyID="EUR"
        )
        category = add(subtotal, CAC, "TaxCategory")
        add(
            category, CBC, "ID",
            "S" if rate > 0 else "Z"
        )
        add(category, CBC, "Percent", str(rate))
        scheme = add(category, CAC, "TaxScheme")
        add(scheme, CBC, "ID", "VAT")

    totals = add(root, CAC, "LegalMonetaryTotal")
    add(
        totals, CBC, "LineExtensionAmount",
        amount(invoice.net_total), currencyID="EUR"
    )
    add(
        totals, CBC, "TaxExclusiveAmount",
        amount(invoice.net_total), currencyID="EUR"
    )
    add(
        totals, CBC, "TaxInclusiveAmount",
        amount(invoice.gross_total), currencyID="EUR"
    )
    add(
        totals, CBC, "PayableAmount",
        amount(invoice.gross_total), currencyID="EUR"
    )

    for line in lines:
        item = add(root, CAC, "InvoiceLine")
        add(item, CBC, "ID", line.position)
        add(
            item, CBC, "InvoicedQuantity",
            str(line.quantity), unitCode="C62"
        )
        add(
            item, CBC, "LineExtensionAmount",
            amount(line.net_total), currencyID="EUR"
        )

        base_net = (
            Decimal(str(line.quantity))
            * Decimal(str(line.unit_net_price))
        ).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        discount = (
            base_net - Decimal(str(line.net_total))
        ).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if discount < 0:
            raise UBLExportError(
                "Positionsbetrag groesser als Basisbetrag."
            )

        if discount > 0:
            allowance = add(item, CAC, "AllowanceCharge")
            add(allowance, CBC, "ChargeIndicator", "false")
            add(
                allowance, CBC, "AllowanceChargeReason",
                "Positionsrabatt"
            )
            add(
                allowance, CBC, "Amount",
                amount(discount), currencyID="EUR"
            )

        product = add(item, CAC, "Item")
        add(product, CBC, "Name", line.description[:100])

        category = add(product, CAC, "ClassifiedTaxCategory")
        rate = Decimal(str(line.vat_rate))
        add(
            category, CBC, "ID",
            "S" if rate > 0 else "Z"
        )
        add(category, CBC, "Percent", str(rate))
        scheme = add(category, CAC, "TaxScheme")
        add(scheme, CBC, "ID", "VAT")

        price = add(item, CAC, "Price")
        add(
            price, CBC, "PriceAmount",
            str(line.unit_net_price), currencyID="EUR"
        )

    return ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
    )
