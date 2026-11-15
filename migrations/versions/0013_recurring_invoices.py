"""Wiederkehrende Rechnungen: Vorlagen, Positionen und Ausfuehrungen.

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recurring_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "partner_id",
            sa.Integer(),
            sa.ForeignKey("partners.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="EUR",
        ),
        sa.Column(
            "xrechnung_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "xrechnung_buyer_reference",
            sa.String(255),
        ),
        sa.Column(
            "interval_months",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "start_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column("end_date", sa.Date()),
        sa.Column(
            "due_days",
            sa.Integer(),
            nullable=False,
            server_default="14",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "interval_months >= 1",
            name="ck_recurring_interval_positive",
        ),
        sa.CheckConstraint(
            "due_days >= 0",
            name="ck_recurring_due_days_nonnegative",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_recurring_date_range",
        ),
    )

    op.create_table(
        "recurring_invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recurring_invoice_id",
            sa.Integer(),
            sa.ForeignKey(
                "recurring_invoices.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "quantity",
            sa.Numeric(14, 3),
            nullable=False,
        ),
        sa.Column(
            "unit",
            sa.String(30),
            nullable=False,
            server_default="Stueck",
        ),
        sa.Column(
            "unit_net_price",
            sa.Numeric(14, 4),
            nullable=False,
        ),
        sa.Column(
            "vat_rate",
            sa.Numeric(5, 2),
            nullable=False,
        ),
        sa.Column(
            "discount_type",
            sa.String(10),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "discount_value",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
        ),
        sa.UniqueConstraint(
            "recurring_invoice_id",
            "position",
            name="uq_recurring_line_position",
        ),
    )

    op.create_table(
        "recurring_invoice_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recurring_invoice_id",
            sa.Integer(),
            sa.ForeignKey(
                "recurring_invoices.id",
                ondelete="SET NULL",
            ),
        ),
        sa.Column(
            "scheduled_date",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            sa.Integer(),
            sa.ForeignKey(
                "invoices.id",
                ondelete="RESTRICT",
            ),
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
        ),
        sa.UniqueConstraint(
            "recurring_invoice_id",
            "scheduled_date",
            name="uq_recurring_run_date",
        ),
        sa.UniqueConstraint(
            "invoice_id",
            name="uq_recurring_run_invoice",
        ),
    )

    op.create_index(
        "ix_recurring_invoices_active",
        "recurring_invoices",
        ["is_active"],
    )

    op.create_index(
        "ix_recurring_runs_status",
        "recurring_invoice_runs",
        ["status"],
    )


def downgrade():
    op.drop_index(
        "ix_recurring_runs_status",
        table_name="recurring_invoice_runs",
    )
    op.drop_index(
        "ix_recurring_invoices_active",
        table_name="recurring_invoices",
    )
    op.drop_table("recurring_invoice_runs")
    op.drop_table("recurring_invoice_lines")
    op.drop_table("recurring_invoices")
