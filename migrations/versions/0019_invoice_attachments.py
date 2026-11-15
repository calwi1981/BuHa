"""Dokumentanhaenge fuer Ausgangsrechnungen.

Revision ID: 0019
Revises: 0018
"""

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoice_attachments",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "invoice_id",
            sa.Integer(),
            sa.ForeignKey(
                "invoices.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "filename",
            sa.String(255),
            nullable=False,
        ),

        sa.Column(
            "mime_type",
            sa.String(100),
            nullable=False,
        ),

        sa.Column(
            "file_size",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "sha256",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "content",
            sa.LargeBinary(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_invoice_attachments_invoice_id",
        "invoice_attachments",
        ["invoice_id"],
    )


def downgrade():
    op.drop_index(
        "ix_invoice_attachments_invoice_id",
        table_name="invoice_attachments",
    )

    op.drop_table("invoice_attachments")
