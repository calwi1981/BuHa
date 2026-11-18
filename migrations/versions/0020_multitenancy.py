from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("tenant_type", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tenant_type IN ('unternehmen', 'vermieter')", name="ck_tenants_type"),
    )


    op.create_table(
        "user_tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_tenants_user_tenant"),
        sa.CheckConstraint("role IN ('admin', 'user')", name="ck_user_tenants_role"),
    )
    op.create_index("ix_user_tenants_user_id", "user_tenants", ["user_id"])
    op.create_index("ix_user_tenants_tenant_id", "user_tenants", ["tenant_id"])


    for table in ("partners", "accounts", "products", "invoices"):
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True))
        op.create_index("ix_" + table + "_tenant_id", table, ["tenant_id"])

    op.create_table(
        "payment_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("opening_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_payment_accounts_tenant_name"),
    )
    op.create_index("ix_payment_accounts_tenant_id", "payment_accounts", ["tenant_id"])
    op.create_index(
        "uq_payment_accounts_one_default_per_tenant",
        "payment_accounts",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )
    op.add_column("payments", sa.Column("payment_account_id", sa.Integer(), sa.ForeignKey("payment_accounts.id", ondelete="RESTRICT"), nullable=True))
    op.create_index("ix_payments_payment_account_id", "payments", ["payment_account_id"])


    # BUHA_BESTANDSDATEN: vorhandene Daten dem ersten Mandanten zuordnen.
    conn = op.get_bind()
    tenant_id = conn.execute(sa.text("INSERT INTO tenants (code, name, tenant_type) VALUES (:code, :name, :type) RETURNING id"), {"code": "calwi.de", "name": "calwi.de", "type": "unternehmen"}).scalar_one()
    conn.execute(
        sa.text("INSERT INTO user_tenants (user_id, tenant_id, role) SELECT id, :tid, 'admin' FROM users WHERE username = :username"),
        {"tid": tenant_id, "username": "mab"},
    )
    for table in ("partners", "accounts", "products", "invoices"):
        conn.execute(sa.text("UPDATE " + table + " SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})
    settings = conn.execute(sa.text("SELECT settings FROM company_settings WHERE id = 1")).scalar_one()
    opening_balance = str(settings.get("bank_opening_balance") or "0")
    opening_date = settings.get("bank_opening_date") or "2026-01-01"
    payment_account_id = conn.execute(sa.text("INSERT INTO payment_accounts (tenant_id, name, opening_balance, opening_date, is_default) VALUES (:tid, :name, :balance, :date, true) RETURNING id"), {"tid": tenant_id, "name": "Bank", "balance": opening_balance, "date": opening_date}).scalar_one()
    conn.execute(sa.text("UPDATE payments SET payment_account_id = :account_id WHERE payment_account_id IS NULL"), {"account_id": payment_account_id})


    # BUHA_MIGRATIONSPRUEFUNG: Mandantenzuordnung kontrollieren.
    user_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM user_tenants ut JOIN users u ON u.id = ut.user_id WHERE u.username = :username AND ut.tenant_id = :tid AND ut.role = 'admin'"),
        {"username": "mab", "tid": tenant_id},
    ).scalar_one()
    if user_count != 1:
        raise RuntimeError("BUHA-Migration abgebrochen: Benutzer mab nicht eindeutig zugeordnet")
    for table in ("partners", "accounts", "products", "invoices"):
        missing = conn.execute(sa.text("SELECT COUNT(*) FROM " + table + " WHERE tenant_id IS NULL")).scalar_one()
        if missing:
            raise RuntimeError("BUHA-Migration abgebrochen: " + table + " enthaelt unzugeordnete Datensaetze")
    missing_payments = conn.execute(sa.text("SELECT COUNT(*) FROM payments WHERE payment_account_id IS NULL")).scalar_one()
    if missing_payments:
        raise RuntimeError("BUHA-Migration abgebrochen: Zahlungen ohne Zahlungskonto")


    # BUHA_RECURRING_TENANTS: bestehende Vorlagen, Positionen und
    # Abrechnungslaeufe dem urspruenglichen Mandanten zuordnen.
    recurring_tables = (
        "recurring_invoices",
        "recurring_invoice_lines",
        "recurring_invoice_runs",
    )
    for table in recurring_tables:
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )
        conn.execute(
            sa.text(
                "UPDATE " + table +
                " SET tenant_id = :tid WHERE tenant_id IS NULL"
            ),
            {"tid": tenant_id},
        )
        missing = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM " + table +
                " WHERE tenant_id IS NULL"
            )
        ).scalar_one()
        if missing:
            raise RuntimeError(
                "BUHA-Migration abgebrochen: " +
                table + " enthaelt unzugeordnete Datensaetze"
            )
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_index(
            "ix_" + table + "_tenant_id",
            table,
            ["tenant_id"],
        )

    # BUHA_TENANT_UNIQUENESS: Nummern je Mandant eindeutig halten.
    for table, column in (("partners", "partner_number"), ("accounts", "number"), ("products", "sku"), ("invoices", "invoice_number")):
        op.drop_constraint(table + "_" + column + "_key", table, type_="unique")
        op.create_unique_constraint("uq_" + table + "_tenant_" + column, table, ["tenant_id", column])
        op.alter_column(table, "tenant_id", nullable=False)


    # BUHA_TENANT_SETTINGS: Einstellungen und Nummernkreise je Mandant.
    for table in ("company_settings", "invoice_sequences"):
        op.add_column(table, sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True))
        conn.execute(sa.text("UPDATE " + table + " SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})
        op.alter_column(table, "tenant_id", nullable=False)
        op.create_index("ix_" + table + "_tenant_id", table, ["tenant_id"])
    op.create_unique_constraint("uq_company_settings_tenant_id", "company_settings", ["tenant_id"])
    op.drop_constraint("uq_invoice_sequence_type_year", "invoice_sequences", type_="unique")
    op.create_unique_constraint("uq_invoice_sequences_tenant_type_year", "invoice_sequences", ["tenant_id", "invoice_type", "year"])


def downgrade():
    for table in (
        "recurring_invoice_runs",
        "recurring_invoice_lines",
        "recurring_invoices",
    ):
        op.drop_index(
            "ix_" + table + "_tenant_id",
            table_name=table,
        )
        op.drop_column(table, "tenant_id")

    op.drop_constraint("uq_invoice_sequences_tenant_type_year", "invoice_sequences", type_="unique")
    op.create_unique_constraint("uq_invoice_sequence_type_year", "invoice_sequences", ["invoice_type", "year"])
    op.drop_constraint("uq_company_settings_tenant_id", "company_settings", type_="unique")
    for table in ("invoice_sequences", "company_settings"):
        op.drop_index("ix_" + table + "_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
    op.drop_index("ix_payments_payment_account_id", table_name="payments")
    op.drop_column("payments", "payment_account_id")
    op.drop_index("ix_payment_accounts_tenant_id", table_name="payment_accounts")
    op.drop_table("payment_accounts")
    for table, column in (("invoices", "invoice_number"), ("products", "sku"), ("accounts", "number"), ("partners", "partner_number")):
        op.drop_constraint("uq_" + table + "_tenant_" + column, table, type_="unique")
        op.create_unique_constraint(table + "_" + column + "_key", table, [column])
    for table in ("invoices", "products", "accounts", "partners"):
        op.drop_index("ix_" + table + "_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
    op.drop_index("ix_user_tenants_tenant_id", table_name="user_tenants")
    op.drop_index("ix_user_tenants_user_id", table_name="user_tenants")
    op.drop_table("user_tenants")
    op.drop_table("tenants")
