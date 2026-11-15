"""Artikelreferenzen wiederkehrender Rechnungen absichern.

Revision ID: 0015
Revises: 0014
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "recurring_invoice_lines_product_id_fkey",
        "recurring_invoice_lines",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "recurring_invoice_lines_product_id_fkey",
        "recurring_invoice_lines",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    op.drop_constraint(
        "recurring_invoice_lines_product_id_fkey",
        "recurring_invoice_lines",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "recurring_invoice_lines_product_id_fkey",
        "recurring_invoice_lines",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )
