"""Create login attempts table.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_attempts",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "username",
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_login_attempts_username",
        "login_attempts",
        ["username"],
    )

    op.create_index(
        "ix_login_attempts_attempted_at",
        "login_attempts",
        ["attempted_at"],
    )


def downgrade():
    op.drop_index(
        "ix_login_attempts_attempted_at",
        table_name="login_attempts",
    )

    op.drop_index(
        "ix_login_attempts_username",
        table_name="login_attempts",
    )

    op.drop_table("login_attempts")
