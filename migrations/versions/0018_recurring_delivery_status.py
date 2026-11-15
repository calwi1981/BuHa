"""Versandstatus wiederkehrender Rechnungen.

Revision ID: 0018
Revises: 0017
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recurring_invoice_runs",
        sa.Column(
            "email_status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "recurring_invoice_runs",
        sa.Column("email_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "recurring_invoice_runs",
        sa.Column(
            "email_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("recurring_invoice_runs", "email_sent_at")
    op.drop_column("recurring_invoice_runs", "email_error")
    op.drop_column("recurring_invoice_runs", "email_status")
