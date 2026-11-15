"""XRechnung fields.

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "partners",
        sa.Column("xrechnung_endpoint", sa.String(320)),
    )
    op.add_column(
        "partners",
        sa.Column("xrechnung_endpoint_scheme", sa.String(10)),
    )
    op.add_column(
        "partners",
        sa.Column("xrechnung_buyer_reference", sa.String(255)),
    )

    op.add_column(
        "invoices",
        sa.Column(
            "xrechnung_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "invoices",
        sa.Column("xrechnung_buyer_reference", sa.String(255)),
    )


def downgrade():
    op.drop_column("invoices", "xrechnung_buyer_reference")
    op.drop_column("invoices", "xrechnung_enabled")
    op.drop_column("partners", "xrechnung_buyer_reference")
    op.drop_column("partners", "xrechnung_endpoint_scheme")
    op.drop_column("partners", "xrechnung_endpoint")
