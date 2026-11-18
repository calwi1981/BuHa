"""Buchungskonto fuer NK-Differenz.

Revision ID: 0025
Revises: 0024
"""

from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoices",
        sa.Column("utility_account_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_invoices_utility_account_id",
        "invoices",
        "accounts",
        ["utility_account_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    op.drop_constraint(
        "fk_invoices_utility_account_id",
        "invoices",
        type_="foreignkey",
    )
    op.drop_column("invoices", "utility_account_id")
