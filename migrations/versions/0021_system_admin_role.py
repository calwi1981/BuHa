from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'system_admin'")


def downgrade():
    raise NotImplementedError("PostgreSQL-ENUM-Wert system_admin kann nicht ohne gesonderte Datenmigration entfernt werden")
