"""Add utility allocation fields to existing invoice lines.

Revision ID: 0024
Revises: 0023
"""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoice_lines",
        sa.Column("utility_total_cost", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "invoice_lines",
        sa.Column("utility_total_key", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "invoice_lines",
        sa.Column("utility_tenant_key", sa.Numeric(18, 6), nullable=True),
    )


def downgrade():
    op.drop_column("invoice_lines", "utility_tenant_key")
    op.drop_column("invoice_lines", "utility_total_key")
    op.drop_column("invoice_lines", "utility_total_cost")
