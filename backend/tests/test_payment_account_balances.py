from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.payment_account_balances import (
    calculate_payment_account_balance,
)


@pytest.mark.parametrize(
    "invoice_type,expected",
    [
        ("outgoing", Decimal("125.00")),
        ("incoming", Decimal("75.00")),
    ],
)
def test_payment_direction(invoice_type, expected):
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        id=1,
        tenant_id=10,
        opening_balance=Decimal("100.00"),
        opening_date=date(2026, 1, 1),
    )
    db.execute.return_value.all.return_value = [
        (Decimal("25.00"), invoice_type),
    ]
    db.scalars.return_value.all.return_value = []

    result = calculate_payment_account_balance(
        db, 10, 1, date(2026, 12, 31)
    )

    assert result == expected


def test_outgoing_transfer():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        id=1,
        tenant_id=10,
        opening_balance=Decimal("100.00"),
        opening_date=date(2026, 1, 1),
    )
    db.execute.return_value.all.return_value = []
    db.scalars.return_value.all.side_effect = [
        [Decimal("30.00")],
        [],
    ]

    assert calculate_payment_account_balance(
        db, 10, 1, date(2026, 12, 31)
    ) == Decimal("70.00")


def test_incoming_transfer():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        id=1,
        tenant_id=10,
        opening_balance=Decimal("100.00"),
        opening_date=date(2026, 1, 1),
    )
    db.execute.return_value.all.return_value = []
    db.scalars.return_value.all.side_effect = [
        [],
        [Decimal("30.00")],
    ]

    assert calculate_payment_account_balance(
        db, 10, 1, date(2026, 12, 31)
    ) == Decimal("130.00")


def test_before_opening_date():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        id=1,
        tenant_id=10,
        opening_balance=Decimal("100.00"),
        opening_date=date(2026, 6, 1),
    )

    result = calculate_payment_account_balance(
        db, 10, 1, date(2026, 5, 31)
    )

    assert result is None
    db.execute.assert_not_called()


def test_foreign_or_missing_account():
    db = MagicMock()
    db.scalar.return_value = None

    result = calculate_payment_account_balance(
        db, 10, 999, date(2026, 12, 31)
    )

    assert result is None
    db.execute.assert_not_called()


def test_tenant_filters_in_queries():
    db = MagicMock()
    db.scalar.return_value = SimpleNamespace(
        id=1,
        tenant_id=10,
        opening_balance=Decimal("100.00"),
        opening_date=date(2026, 1, 1),
    )
    db.execute.return_value.all.return_value = []
    db.scalars.return_value.all.return_value = []

    calculate_payment_account_balance(
        db, 10, 1, date(2026, 12, 31)
    )

    payment_query = db.execute.call_args.args[0]
    assert "invoices.tenant_id" in str(payment_query)
    assert "payments.payment_account_id" in str(payment_query)

    transfer_queries = [
        call.args[0]
        for call in db.scalars.call_args_list
    ]

    assert len(transfer_queries) == 2

    for query in transfer_queries:
        assert "payment_account_transfers.tenant_id" in str(query)
