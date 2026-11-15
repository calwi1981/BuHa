"""BUHA Administration und Rechnungsnummern"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settings", JSONB(), nullable=False),
        sa.Column("logo", sa.LargeBinary(), nullable=True),
        sa.Column("logo_mime", sa.String(30), nullable=True),
    )

    op.execute("""
        INSERT INTO company_settings (id, settings)
        VALUES (1, '{}'::jsonb)
    """)

    op.add_column(
        "invoices",
        sa.Column("supplier_reference", sa.String(100), nullable=True),
    )


def downgrade():
    op.drop_column("invoices", "supplier_reference")
    op.drop_table("company_settings")
