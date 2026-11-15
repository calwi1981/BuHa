"""Invoice line discounts

Revision ID: 0009
Revises: 0008
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoice_lines",
        sa.Column(
            "discount_type",
            sa.String(10),
            nullable=False,
            server_default="none",
        ),
    )

    op.add_column(
        "invoice_lines",
        sa.Column(
            "discount_value",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade():
    op.drop_column("invoice_lines", "discount_value")
    op.drop_column("invoice_lines", "discount_type")
