"""Mandantenbezogene manuelle Einnahmen und Ausgaben.

Revision ID: 0026
Revises: 0025
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "manual_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "booking_number", sa.String(100), nullable=False,
        ),
        sa.Column(
            "booking_type", sa.String(20), nullable=False,
        ),
        sa.Column(
            "booking_date", sa.Date(), nullable=False,
        ),
        sa.Column(
            "amount", sa.Numeric(14, 2), nullable=False,
        ),
        sa.Column(
            "payment_account_id", sa.Integer(),
            sa.ForeignKey("payment_accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "account_id", sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "booking_number",
            name="uq_manual_bookings_tenant_number",
        ),
        sa.CheckConstraint(
            "booking_type IN ('income', 'expense')",
            name="ck_manual_bookings_type",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_manual_bookings_positive_amount",
        ),
    )
    op.create_index(
        "ix_manual_bookings_tenant_id",
        "manual_bookings",
        ["tenant_id"],
    )


def downgrade():
    op.drop_index(
        "ix_manual_bookings_tenant_id",
        table_name="manual_bookings",
    )
    op.drop_table("manual_bookings")
