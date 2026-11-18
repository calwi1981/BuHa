"""BUHA V1.2.0: Mandantensichere Zahlungskonten-Umbuchungen."""

from alembic import op
import sqlalchemy as sa


revision = "0022_payment_account_transfers"
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint(
        "uq_payment_accounts_tenant_id_id",
        "payment_accounts",
        ["tenant_id", "id"],
    )

    op.create_table(
        "payment_account_transfers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("source_account_id", sa.Integer(), nullable=False),
        sa.Column("target_account_id", sa.Integer(), nullable=False),
        sa.Column("transfer_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_payment_transfers_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_account_id"],
            ["payment_accounts.tenant_id", "payment_accounts.id"],
            name="fk_payment_transfers_source_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_account_id"],
            ["payment_accounts.tenant_id", "payment_accounts.id"],
            name="fk_payment_transfers_target_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_payment_account_transfers_positive_amount",
        ),
        sa.CheckConstraint(
            "source_account_id <> target_account_id",
            name="ck_payment_account_transfers_distinct_accounts",
        ),
    )

    op.create_index(
        "ix_payment_account_transfers_tenant_id",
        "payment_account_transfers",
        ["tenant_id"],
    )
    op.create_index(
        "ix_payment_account_transfers_source_account_id",
        "payment_account_transfers",
        ["source_account_id"],
    )
    op.create_index(
        "ix_payment_account_transfers_target_account_id",
        "payment_account_transfers",
        ["target_account_id"],
    )


def downgrade():
    op.drop_index(
        "ix_payment_account_transfers_target_account_id",
        table_name="payment_account_transfers",
    )
    op.drop_index(
        "ix_payment_account_transfers_source_account_id",
        table_name="payment_account_transfers",
    )
    op.drop_index(
        "ix_payment_account_transfers_tenant_id",
        table_name="payment_account_transfers",
    )
    op.drop_table("payment_account_transfers")
    op.drop_constraint(
        "uq_payment_accounts_tenant_id_id",
        "payment_accounts",
        type_="unique",
    )
