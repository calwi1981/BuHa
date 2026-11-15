
"""Persistente BUHA-Rechnungsnummernkreise"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice_sequences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_type", sa.String(20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "invoice_type",
            "year",
            name="uq_invoice_sequence_type_year",
        ),
    )

    op.execute("""
        INSERT INTO invoice_sequences
            (invoice_type, year, last_number)
        VALUES
            ('outgoing', 2026, 31),
            ('incoming', 2026, 75)
    """)


def downgrade():
    op.drop_table("invoice_sequences")
