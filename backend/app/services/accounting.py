from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _allocate_total(amount, invoice_gross, lines):
    amount = money(amount)
    invoice_gross = money(invoice_gross)

    if invoice_gross <= 0:
        raise ValueError("Rechnungsbetrag muss positiv sein.")

    if amount < 0 or amount > invoice_gross:
        raise ValueError("Ungueltiger Zahlungsbetrag.")

    if not lines:
        raise ValueError("Rechnung hat keine Positionen.")

    gross_sum = sum(
        (money(line.gross_total) for line in lines),
        Decimal("0"),
    )

    if money(gross_sum) != invoice_gross:
        raise ValueError("Rechnungspositionen stimmen nicht ueberein.")

    result = []
    allocated_gross = Decimal("0")
    allocated_net = Decimal("0")
    invoice_net = sum(
        (money(line.net_total) for line in lines), Decimal("0")
    )
    target_net = money(amount * invoice_net / invoice_gross)

    for index, line in enumerate(lines):
        line_gross = money(line.gross_total)
        line_net = money(line.net_total)

        if amount == invoice_gross:
            gross = line_gross
            net = line_net
        elif index == len(lines) - 1:
            gross = money(amount - allocated_gross)
            net = money(target_net - allocated_net)
        else:
            gross = money(amount * line_gross / invoice_gross)
            net = money(amount * line_net / invoice_gross)

        vat = money(gross - net)
        allocated_gross += gross
        allocated_net += net

        result.append({
            "account_id": line.account_id,
            "description": line.description,
            "vat_rate": line.vat_rate,
            "net": net,
            "vat": vat,
            "gross": gross,
        })

    return result


def allocate_payment(payment_amount, invoice_gross, lines, previously_paid=0):
    payment_amount = money(payment_amount)
    previously_paid = money(previously_paid)
    invoice_gross = money(invoice_gross)

    if payment_amount <= 0:
        raise ValueError("Zahlungsbetrag muss positiv sein.")

    if previously_paid < 0:
        raise ValueError("Bisherige Zahlungen ungueltig.")

    if money(previously_paid + payment_amount) > invoice_gross:
        raise ValueError("Zahlung uebersteigt Rechnungsbetrag.")

    before = _allocate_total(previously_paid, invoice_gross, lines)
    after = _allocate_total(
        previously_paid + payment_amount,
        invoice_gross,
        lines,
    )

    result = []

    for old, new in zip(before, after):
        result.append({
            "account_id": new["account_id"],
            "description": new["description"],
            "vat_rate": new["vat_rate"],
            "net": money(new["net"] - old["net"]),
            "vat": money(new["vat"] - old["vat"]),
            "gross": money(new["gross"] - old["gross"]),
        })

    assert money(sum(
        (row["gross"] for row in result),
        Decimal("0"),
    )) == payment_amount

    return result
