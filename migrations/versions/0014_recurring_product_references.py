"""Wiederkehrende Rechnungspositionen referenzieren Artikelstammdaten.

Revision ID: 0014
Revises: 0013
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    count = connection.execute(
        sa.text("SELECT count(*) FROM recurring_invoice_lines")
    ).scalar_one()

    if count:
        raise RuntimeError(
            "Migration 0014 erfordert leere wiederkehrende Positionen."
        )

    with op.batch_alter_table("recurring_invoice_lines") as batch:
        batch.alter_column(
            "product_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

        for name in (
            "description",
            "unit",
            "unit_net_price",
            "vat_rate",
            "discount_type",
            "discount_value",
            "account_id",
        ):
            batch.drop_column(name)


def downgrade():
    raise RuntimeError(
        "Automatischer Rueckbau von 0014 ist nicht vorgesehen."
    )
