"""Add utility billing fields to existing invoices.

Revision ID: 0023
Revises: 0022
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022_payment_account_transfers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoices",
        sa.Column("utility_period_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("utility_period_to", sa.Date(), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("utility_prepayments", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("utility_total_cost", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("utility_difference", sa.Numeric(12, 2), nullable=True),
    )


def downgrade():
    op.drop_column("invoices", "utility_difference")
    op.drop_column("invoices", "utility_total_cost")
    op.drop_column("invoices", "utility_prepayments")
    op.drop_column("invoices", "utility_period_to")
    op.drop_column("invoices", "utility_period_from")
