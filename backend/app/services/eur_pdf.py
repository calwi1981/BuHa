"""PDF-Export der bestehenden BUHA-EÜR-Auswertung."""

from io import BytesIO
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, KeepTogether,
)

NAVY = colors.HexColor("#171b42")
LIGHT = colors.HexColor("#e8e8ed")


def fmt(value):
    amount = Decimal(str(value or 0))
    return (
        f"{amount:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def safe(value):
    return escape(str(value if value is not None else ""))


def render_eur_pdf(data, view="details"):
    if view not in {"details", "summary"}:
        raise ValueError("Ungueltige EÜR-PDF-Darstellung.")

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title="BUHA Einnahmen-Ueberschuss-Rechnung",
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="EurTitle",
        parent=styles["Heading1"],
        fontSize=15,
        leading=19,
        textColor=NAVY,
        spaceAfter=10,
    ))

    styles.add(ParagraphStyle(
        name="EurGroup",
        parent=styles["Heading2"],
        fontSize=10,
        leading=13,
        textColor=NAVY,
        spaceBefore=12,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="EurCell",
        fontName="Helvetica",
        fontSize=7,
        leading=9,
    ))

    styles.add(ParagraphStyle(
        name="EurCellRight",
        parent=styles["EurCell"],
        alignment=TA_RIGHT,
    ))

    story = []

    def text_cell(value, right=False):
        return Paragraph(
            safe(value),
            styles["EurCellRight" if right else "EurCell"],
        )

    def add_table(headers, rows, widths):
        matrix = [
            [text_cell(header) for header in headers]
        ]

        matrix.extend(rows)

        table = Table(
            matrix,
            colWidths=widths,
            repeatRows=1,
            hAlign="LEFT",
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, NAVY),
            ("LINEBELOW", (0, 1), (-1, -1), 0.2, LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))

        story.append(table)

    story.append(Paragraph(
        "Einnahmen-Überschuss-Rechnung (EÜR)",
        styles["EurTitle"],
    ))

    story.append(Paragraph(
        "Zeitraum: " +
        safe(data.get("date_from")) +
        " bis " +
        safe(data.get("date_to")),
        styles["Normal"],
    ))

    story.append(Spacer(1, 8))

    overview = [
        ["Einnahmen netto", fmt(data.get("income_net")) + " EUR"],
        ["Ausgaben netto", fmt(data.get("expenses_net")) + " EUR"],
        ["Ergebnis netto", fmt(data.get("result_net")) + " EUR"],
        ["Vereinnahmte Umsatzsteuer",
         fmt(data.get("output_vat_total")) + " EUR"],
        ["Beruecksichtigte Vorsteuer",
         fmt(data.get("input_vat_total")) + " EUR"],
        ["Umsatzsteuerdifferenz",
         fmt(data.get("vat_difference")) + " EUR"],
    ]

    add_table(
        ["Kennzahl", "Betrag"],
        [
            [text_cell(label), text_cell(amount, True)]
            for label, amount in overview
        ],
        [115 * mm, 45 * mm],
    )

    story.append(Spacer(1, 10))

    if view == "summary":
        story.append(Paragraph(
            "Auswertung nach Buchhaltungskonten",
            styles["EurGroup"],
        ))

        rows = []

        for item in data.get("accounts", []):
            kind = (
                "Einnahme"
                if item.get("invoice_type") == "outgoing"
                else "Ausgabe"
            )

            rows.append([
                text_cell(kind),
                text_cell(item.get("account_number")),
                text_cell(item.get("account_name")),
                text_cell(fmt(item.get("net")), True),
                text_cell(fmt(item.get("vat")), True),
                text_cell(fmt(item.get("gross")), True),
            ])

        if rows:
            add_table(
                ["Art", "Konto", "Bezeichnung",
                 "Netto", "USt", "Brutto"],
                rows,
                [27 * mm, 23 * mm, 91 * mm,
                 36 * mm, 36 * mm, 36 * mm],
            )
        else:
            story.append(Paragraph(
                "Keine Buchungen im gewaehlten Zeitraum.",
                styles["Normal"],
            ))

    else:
        story.append(Paragraph(
            "Alle Einzelbuchungen",
            styles["EurGroup"],
        ))

        groups = data.get("detail_groups", [])

        if not groups:
            story.append(Paragraph(
                "Keine Buchungen im gewaehlten Zeitraum.",
                styles["Normal"],
            ))

        for group in groups:
            group_title = Paragraph(
                safe(group.get("group")),
                styles["EurGroup"],
            )

            rows = []

            for item in group.get("rows", []):
                kind = (
                    "Einnahme"
                    if item.get("invoice_type") == "outgoing"
                    else "Ausgabe"
                )

                rows.append([
                    text_cell(item.get("payment_date")),
                    text_cell(item.get("invoice_number")),
                    text_cell(kind),
                    text_cell(item.get("account_number")),
                    text_cell(item.get("description")),
                    text_cell(fmt(item.get("net")), True),
                    text_cell(fmt(item.get("vat")), True),
                    text_cell(fmt(item.get("gross")), True),
                ])

            rows.append([
                text_cell("Summe"),
                text_cell(""),
                text_cell(""),
                text_cell(""),
                text_cell(""),
                text_cell(fmt(group.get("net")), True),
                text_cell(fmt(group.get("vat")), True),
                text_cell(fmt(group.get("gross")), True),
            ])

            headers = [
                "Datum", "Rechnung", "Art", "Konto",
                "Beschreibung", "Netto", "USt", "Brutto",
            ]

            widths = [
                23 * mm, 30 * mm, 24 * mm, 20 * mm,
                62 * mm, 30 * mm, 30 * mm, 30 * mm,
            ]

            story.append(KeepTogether([
                group_title,
                Spacer(1, 2),
            ]))

            add_table(headers, rows, widths)

            story.append(Spacer(1, 7))

    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Hinweis: Zahlungsbasierte Auswertung. "
        "Die Umsatzsteueruebersicht ersetzt keine "
        "Umsatzsteuer-Voranmeldung.",
        styles["Normal"],
    ))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(NAVY)
        canvas.drawRightString(
            landscape(A4)[0] - 14 * mm,
            9 * mm,
            f"Seite {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
    )

    return output.getvalue()
