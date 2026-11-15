"""Account tax settings

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounts",
        sa.Column(
            "default_vat_rate",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "accounts",
        sa.Column(
            "tax_treatment",
            sa.String(30),
            nullable=False,
            server_default="none",
        ),
    )

    op.add_column(
        "accounts",
        sa.Column(
            "input_vat_deductible_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="100",
        ),
    )


    # BUHA_ACCOUNT_TAX_DEFAULTS
    # Initialwerte aus den importierten Rechnungspositionen.
    # Historische Rechnungspositionen bleiben unveraendert.
    op.execute("""
        UPDATE accounts
        SET
            default_vat_rate = CASE number
                WHEN '34' THEN 19
                WHEN '46' THEN 19
                WHEN '493' THEN 19
                WHEN '4935' THEN 19
                WHEN '84' THEN 19
                ELSE 0
            END,
            tax_treatment = CASE
                WHEN number = '84' THEN 'output_vat'
                WHEN number IN ('34', '46', '493', '4935')
                    THEN 'input_vat'
                ELSE 'none'
            END,
            input_vat_deductible_percent = CASE
                WHEN number IN ('34', '46', '493', '4935')
                    THEN 100
                ELSE 0
            END
        WHERE number IN (
            '18', '34', '344', '4376',
            '46', '493', '4935', '84'
        )
    """)


def downgrade():
    op.drop_column("accounts", "input_vat_deductible_percent")
    op.drop_column("accounts", "tax_treatment")
    op.drop_column("accounts", "default_vat_rate")
