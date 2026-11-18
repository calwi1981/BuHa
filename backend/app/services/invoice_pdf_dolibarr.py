"""BUHA-Rechnungs-PDF im Layout der Dolibarr-Referenz."""
from collections import defaultdict
from decimal import Decimal
from io import BytesIO

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

NAVY = colors.HexColor("#171b42")
GRAY = colors.HexColor("#777777")
LIGHT = colors.HexColor("#e8e8ed")
W, H = A4
LEFT, RIGHT = 30, W - 30


def money(value):
    return (
        f"{Decimal(str(value or 0)):,.2f}"
        .replace(",", "X").replace(".", ",").replace("X", ".")
    )


def number(value):
    value = Decimal(str(value or 0))
    return format(value.normalize(), "f")


def txt(value):
    return str(value or "").replace("\r", "").replace("\t", " ")


def draw(c, x, y, value, size=8, bold=False, right=False,
         color=NAVY):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    method = c.drawRightString if right else c.drawString
    method(x, y, txt(value))


def wrapped(c, value, x, y, width, size=8, leading=11,
            bold=False, max_y=None):
    font = "Helvetica-Bold" if bold else "Helvetica"
    for paragraph in txt(value).split("\n"):
        words = paragraph.split()
        if not words:
            y -= leading
            continue
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if c.stringWidth(candidate, font, size) > width and current:
                if max_y is not None and y < max_y:
                    return y
                draw(c, x, y, current, size, bold)
                y -= leading
                current = word
            else:
                current = candidate
        if current:
            if max_y is not None and y < max_y:
                return y
            draw(c, x, y, current, size, bold)
            y -= leading
    return y


def qr_image(settings, invoice):
    if (
        invoice.utility_period_from is not None
        and (
            invoice.utility_difference is None
            or Decimal(str(invoice.utility_difference)) <= 0
        )
    ):
        return None

    iban = "".join(txt(settings.get("iban")).split())
    bic = "".join(txt(settings.get("bic")).split())
    holder = txt(
        settings.get("bank_holder") or settings.get("company_name")
    )
    if not iban or not holder:
        return None
    payload = "\n".join([
        "BCD", "002", "1", "SCT", bic, holder[:70],
        iban, f"EUR{Decimal(str(invoice.utility_difference if invoice.utility_period_from is not None else invoice.gross_total)):.2f}",
        "", "", txt(invoice.invoice_number)[:140], ""
    ])
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=5, border=2
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output


def render_invoice_pdf(invoice, partner, lines, payments,
                       settings, logo=None):
    output = BytesIO()
    c = canvas.Canvas(output, pagesize=A4)
    c.setTitle(f"Rechnung {invoice.invoice_number}")

    company = txt(settings.get("company_name"))
    street = txt(settings.get("street"))
    place = " ".join(filter(None, [
        txt(settings.get("postal_code")),
        txt(settings.get("city"))
    ]))
    recipient_place = " ".join(filter(None, [
        txt(partner.postal_code), txt(partner.city)
    ]))

    paid = sum(
        (Decimal(str(p.amount)) for p in payments),
        Decimal("0")
    )
    balance = Decimal(str(
        invoice.utility_difference
        if invoice.utility_period_from is not None
        else invoice.gross_total
    )) - paid

    def footer(page):
        c.setStrokeColor(LIGHT)
        c.setLineWidth(0.5)
        c.line(30, 60, W - 30, 60)
        lines_footer = [
            "Firmensitz: " + " - ".join(filter(None, [
                company, street, place,
                txt(settings.get("country"))
            ])),
            " - ".join(filter(None, [
                "Telefon: " + txt(settings.get("phone"))
                if settings.get("phone") else "",
                "Fax: " + txt(settings.get("fax"))
                if settings.get("fax") else "",
                txt(settings.get("website")),
                txt(settings.get("email"))
            ])),
            " - ".join(filter(None, [
                "Steuernummer: " + txt(settings.get("tax_number"))
                if settings.get("tax_number") else "",
                "USt-IdNr.: " + txt(settings.get("vat_id"))
                if settings.get("vat_id") else ""
            ])),
            txt(settings.get("invoice_footer"))
        ]
        y = 49
        for line in lines_footer:
            if line:
                font = "Helvetica"
                size = 6.2
                while c.stringWidth(line, font, size) > W - 90 and size > 4.5:
                    size -= 0.2
                c.setFont(font, size)
                c.setFillColor(NAVY)
                c.drawCentredString(W / 2, y, line)
                y -= 9
        draw(c, W - 30, 14, f"{page}", 7, right=True)

    def heading(first_page=True):
        if first_page:
            if logo:
                try:
                    reader = ImageReader(BytesIO(logo))
                    iw, ih = reader.getSize()
                    scale = min(166 / iw, 61 / ih)
                    c.drawImage(
                        reader, LEFT, H - 78,
                        width=iw * scale,
                        height=ih * scale,
                        preserveAspectRatio=True,
                        mask="auto"
                    )
                except Exception:
                    pass

            draw(c, RIGHT, H - 29,
                 f"Rechnung {invoice.invoice_number}",
                 13, True, True)
            draw(c, RIGHT, H - 55,
                 "Rechnungsdatum : "
                 + invoice.invoice_date.strftime("%d.%m.%Y"),
                 7.4, right=True)
            if invoice.due_date:
                draw(c, RIGHT, H - 66,
                     "Fälligkeitsdatum : "
                     + invoice.due_date.strftime("%d.%m.%Y"),
                     7.4, right=True)
            draw(c, RIGHT, H - 77,
                 "Kundennummer : " + txt(partner.partner_number),
                 7.4, right=True)

            draw(c, 40, H - 116, partner.name, 9, True)
            draw(c, 40, H - 129, partner.street, 8)
            draw(c, 40, H - 141, recipient_place, 8)
            if partner.notes:
                wrapped(c, partner.notes, 40, H - 164,
                        250, 7.5, 10, max_y=H - 207)

            draw(c, 365, H - 116, company, 9, True)
            draw(c, 365, H - 129, street, 8)
            draw(c, 365, H - 141, place, 8)

            contact = []
            if settings.get("phone"):
                contact.append("Tel.: " + txt(settings["phone"]))
            if settings.get("fax"):
                contact.append("Fax: " + txt(settings["fax"]))
            if contact:
                wrapped(c, " - ".join(contact),
                        365, H - 166, 195, 7.4, 10)
            if settings.get("email"):
                draw(c, 365, H - 189,
                     "E-Mail: " + txt(settings["email"]), 7.4)
            if settings.get("website"):
                draw(c, 365, H - 201,
                     "Internet: " + txt(settings["website"]), 7.4)

            qr = qr_image(settings, invoice)
            if qr:
                c.drawImage(
                    ImageReader(qr), 30, H - 306,
                    width=84, height=84
                )
                draw(c, 124, H - 250,
                     "Girocode/EPC-QR-Code", 6.6)
                wrapped(
                    c,
                    "Scannen Sie diesen QR-Code mit Ihrer "
                    "Banking-App, um die SEPA-Überweisung "
                    "bequem auszuführen.",
                    124, H - 263, 145, 6.3, 8
                )
            return H - 331

        draw(c, 30, H - 37,
             f"Rechnung {invoice.invoice_number} – Fortsetzung",
             10, True)
        return H - 62

    cols = [30, 290, 339, 396, 449, 515, W - 30]
    headers = [
        "Beschreibung", "USt.", "EP (netto)",
        "Anz.", "Nettosumme", "Gesamt (inkl. USt)"
    ]

    def table_header(y):
        draw(c, LEFT, y + 10,
             "Alle Beträge in Euro", 7, right=False)
        c.setStrokeColor(GRAY)
        c.setLineWidth(0.45)
        c.rect(LEFT, y - 19, RIGHT - LEFT, 20, stroke=1, fill=0)
        for x in cols[1:-1]:
            c.line(x, y + 1, x, y - 19)
        for i, name in enumerate(headers):
            if i == 0:
                draw(c, cols[i] + 3, y - 12, name, 7.1)
            else:
                size = 6.4 if i == 5 else 6.8
                draw(c, cols[i + 1] - 3, y - 12,
                     name, size, right=True)
        return y - 19

    def table_segment(y, height):
        c.setStrokeColor(GRAY)
        c.setLineWidth(0.45)
        c.line(LEFT, y, RIGHT, y)
        c.line(LEFT, y - height, RIGHT, y - height)
        c.line(LEFT, y, LEFT, y - height)
        c.line(RIGHT, y, RIGHT, y - height)
        for x in cols[1:-1]:
            c.line(x, y, x, y - height)

    def line_height(line):
        desc = txt(line.description)
        approx_lines = sum(
            max(1, (len(part) + 47) // 48)
            for part in desc.split("\n")
        )
        discount = Decimal(str(getattr(line, "discount_value", 0) or 0))
        return max(31, 9 + approx_lines * 10 + (11 if discount > 0 else 0))

    y = heading()
    y = table_header(y)
    page = 1
    position_y = y

    for line in lines:
        needed = line_height(line)
        if y - needed < 245:
            table_segment(position_y, max(0, position_y - y))
            footer(page)
            c.showPage()
            page += 1
            y = table_header(heading(False))
            position_y = y

        desc_y = wrapped(
            c, line.description, cols[0] + 4, y - 13,
            cols[1] - cols[0] - 9, 7.8, 10,
            max_y=y - needed + 3
        )
        discount = Decimal(str(
            getattr(line, "discount_value", 0) or 0
        ))
        if discount > 0:
            dtype = getattr(line, "discount_type", "none")
            suffix = "%" if dtype == "percent" else "EUR"
            draw(c, cols[0] + 4, desc_y - 1,
                 f"Rabatt: {money(discount)} {suffix}", 7)

        vals = [
            f"{number(line.vat_rate)}%",
            money(line.unit_net_price),
            number(line.quantity),
            money(line.net_total),
            money(line.gross_total)
        ]
        for i, value in enumerate(vals, 1):
            draw(c, cols[i + 1] - 3, y - 13,
                 value, 7.4, right=True)
        y -= needed

    # Wie in der Referenz: hoher Positionsrahmen,
    # soweit der verbleibende Platz dies erlaubt.
    if page == 1:
        target_bottom = 267
        if y > target_bottom:
            y = target_bottom

    table_segment(position_y, max(0, position_y - y))

    # Auf Folgeseiten wird der Summenblock separat ausgegeben.
    if y < 218:
        footer(page)
        c.showPage()
        page += 1
        y = H - 70

    summary_top = y - 15
    left_x = 32
    right_x = 358

    # Umsatzsteuer nach Steuersatz zusammenfassen.
    taxes = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for line in lines:
        key = Decimal(str(line.vat_rate))
        taxes[key][0] += Decimal(str(line.net_total))
        taxes[key][1] += Decimal(str(line.vat_total))

    draw(c, left_x, summary_top,
         "USt.          Nettosumme        USt.-Betrag       Gesamtbetrag",
         6.8, True)
    tax_y = summary_top - 12
    for rate, (net, tax) in sorted(taxes.items()):
        draw(c, left_x, tax_y, f"{number(rate)}%", 7)
        draw(c, 142, tax_y, money(net), 7, right=True)
        draw(c, 225, tax_y, money(tax), 7, right=True)
        draw(c, 314, tax_y, money(net + tax), 7, right=True)
        tax_y -= 11

    totals = [
        ("Nettosumme", invoice.net_total),
        ("USt. gesamt", invoice.vat_total),
        ("Bruttosumme", invoice.gross_total),
        ("Bezahlt", paid),
        ("Offener Zahlbetrag", balance)
    ]
    sy = summary_top
    for label, value in totals:
        if label in {"Bruttosumme", "Offener Zahlbetrag"}:
            c.setFillColor(LIGHT)
            c.rect(right_x - 2, sy - 4, RIGHT - right_x + 2,
                   12, stroke=0, fill=1)
        draw(c, right_x, sy, label, 7.6,
             label in {"Bruttosumme", "Offener Zahlbetrag"})
        draw(c, RIGHT, sy, money(value), 7.6,
             label in {"Bruttosumme", "Offener Zahlbetrag"},
             right=True)
        sy -= 13

    if invoice.utility_period_from is not None:
        nk_cost = Decimal(str(invoice.utility_total_cost))
        nk_advance = Decimal(str(invoice.utility_prepayments))
        nk_difference = Decimal(str(invoice.utility_difference))

        nk_rows = [
            ("Nebenkosten gesamt", nk_cost),
            ("Abzgl. Vorauszahlungen", -nk_advance),
        ]

        if nk_difference > 0:
            nk_rows.append(("Nachzahlung", nk_difference))
        elif nk_difference < 0:
            nk_rows.append(("Guthaben", -nk_difference))
        else:
            nk_rows.append(("Ausgeglichen", Decimal("0")))

        if balance > 0:
            nk_rows.append(("Noch zu zahlen", balance))
        elif balance < 0:
            nk_rows.append(("Noch auszuzahlen", -balance))
        else:
            nk_rows.append(("Offener Saldo", Decimal("0")))

        nk_y = min(tax_y - 24, sy - 18)

        if nk_y - len(nk_rows) * 15 < 85:
            footer(page)
            c.showPage()
            page += 1
            nk_y = H - 90

        draw(c, right_x, nk_y,
             "Nebenkostenabrechnung", 8, True)
        nk_y -= 17

        for label, value in nk_rows:
            draw(c, right_x, nk_y, label, 7)
            draw(c, RIGHT, nk_y, money(value),
                 7, right=True)
            nk_y -= 15

        tax_y = min(tax_y, nk_y - 8)

    bank_y = tax_y - 12
    if invoice.due_date:
        days = (invoice.due_date - invoice.invoice_date).days
        draw(c, left_x, bank_y,
             f"Zahlungsbedingungen: {days} Tage", 7)
        bank_y -= 18

    if any(settings.get(k) for k in
           ("bank_name", "bank_holder", "iban", "bic")):
        draw(c, left_x, bank_y,
             "Zahlung per Überweisung bitte auf folgendes Konto:",
             7, True)
        bank_y -= 13
        for label, key in [
            ("Bank", "bank_name"),
            ("Kontoinhaber", "bank_holder"),
            ("IBAN", "iban"),
            ("BIC / SWIFT-Code", "bic")
        ]:
            if settings.get(key):
                draw(c, left_x, bank_y,
                     f"{label}: {settings[key]}", 6.8,
                     key in {"iban", "bic"})
                bank_y -= 10

    if payments:
        py = sy - 12
        draw(c, right_x, py, "Bereits getätigte Zahlungen", 7, True)
        py -= 13
        draw(c, right_x, py,
             "Zahlung          Betrag          Typ", 6.6)
        py -= 10
        for payment in payments:
            if py < 78:
                footer(page)
                c.showPage()
                page += 1
                py = H - 55
            draw(c, right_x, py,
                 payment.payment_date.strftime("%d.%m.%Y"), 6.5)
            draw(c, right_x + 92, py,
                 money(payment.amount), 6.5, right=True)
            wrapped(c, payment.payment_method,
                    right_x + 104, py, 100, 6.5, 9)
            py -= 12

    if invoice.notes:
        note_y = min(bank_y - 14, 118)
        if note_y > 72:
            wrapped(c, invoice.notes, left_x, note_y,
                    300, 7, 9, max_y=68)

    footer(page)
    c.save()
    return output.getvalue()
