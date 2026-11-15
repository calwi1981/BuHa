"""Dolibarr-Importzuordnungen"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dolibarr_import_map",
        sa.Column(
            "id", sa.Integer(), primary_key=True
        ),
        sa.Column(
            "source_table", sa.String(100),
            nullable=False
        ),
        sa.Column(
            "source_id", sa.BigInteger(),
            nullable=False
        ),
        sa.Column(
            "target_table", sa.String(100),
            nullable=False
        ),
        sa.Column(
            "target_id", sa.Integer(),
            nullable=False
        ),
        sa.UniqueConstraint(
            "source_table", "source_id",
            name="uq_dolibarr_source"
        ),
        sa.UniqueConstraint(
            "target_table", "target_id",
            name="uq_dolibarr_target"
        ),
    )


def downgrade():
    op.drop_table("dolibarr_import_map")
