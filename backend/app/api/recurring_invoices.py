"""Verwaltung wiederkehrender Ausgangsrechnungsvorlagen."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from app.api.dependencies import TenantUser, DatabaseSession
from app.models.partner import Partner
from app.models.product import Product
from app.services.recurring_schedule import next_occurrence

router = APIRouter(
    prefix="/api/recurring-invoices",
    tags=["Wiederkehrende Rechnungen"],
)


class RecurringLineData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    quantity: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=3,
    )


class RecurringInvoiceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    partner_id: int = Field(gt=0)
    notes: str | None = None
    xrechnung_enabled: bool = False
    xrechnung_buyer_reference: str | None = Field(
        default=None,
        max_length=255,
    )
    interval_months: int = Field(ge=1, le=1200)
    start_date: date
    end_date: date | None = None
    due_days: int = Field(default=14, ge=0, le=3650)
    is_active: bool = True
    lines: list[RecurringLineData] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("Enddatum liegt vor dem Startdatum.")
        return self


class ActiveData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


def validate_references(db, tenant_id, data):
    partner = db.get(Partner, data.partner_id)

    if (
        partner is None
        or partner.tenant_id != tenant_id
        or not partner.is_active
        or not partner.is_customer
    ):
        raise HTTPException(
            422,
            "Aktiver Kunde nicht vorhanden.",
        )

    for line in data.lines:
        product = db.get(Product, line.product_id)

        if product is None or product.tenant_id != tenant_id or not product.is_active:
            raise HTTPException(
                422,
                "Artikel nicht vorhanden oder inaktiv.",
            )


def load_template(db, tenant_id, template_id):
    row = db.execute(
        text("""
            SELECT id, name, partner_id, notes, currency,
                   xrechnung_enabled, xrechnung_buyer_reference,
                   interval_months, start_date, end_date,
                   due_days, is_active, created_at, updated_at
            FROM recurring_invoices
            WHERE id = :id AND tenant_id = :tenant_id
        """),
        {"id": template_id, "tenant_id": tenant_id},
    ).mappings().first()

    if row is None:
        raise HTTPException(404, "Vorlage nicht gefunden.")

    result = dict(row)

    lines = db.execute(
        text("""
            SELECT id, position, product_id, quantity
            FROM recurring_invoice_lines
            WHERE recurring_invoice_id = :id AND tenant_id = :tenant_id
            ORDER BY position
        """),
        {"id": template_id, "tenant_id": tenant_id},
    ).mappings().all()

    result["lines"] = [dict(line) for line in lines]

    last_run = db.execute(
        text("""
            SELECT max(scheduled_date)
            FROM recurring_invoice_runs
            WHERE recurring_invoice_id = :id AND tenant_id = :tenant_id
              AND invoice_id IS NOT NULL
        """),
        {"id": template_id, "tenant_id": tenant_id},
    ).scalar_one()

    result["last_generated_date"] = last_run

    result["next_date"] = (
        next_occurrence(
            result["start_date"],
            result["interval_months"],
            after_date=last_run,
            end_date=result["end_date"],
        )
        if result["is_active"] else None
    )

    return result


@router.get("")
def list_templates(db: DatabaseSession, tenant: TenantUser):
    ids = db.execute(
        text("""
            SELECT id
            FROM recurring_invoices
            WHERE tenant_id = :tenant_id
            ORDER BY id DESC
        """),
        {"tenant_id": tenant.tenant_id}
    ).scalars().all()

    return [load_template(db, tenant.tenant_id, template_id) for template_id in ids]


@router.get("/{template_id}")
def get_template(
    template_id: int,
    db: DatabaseSession,
    tenant: TenantUser,
):
    return load_template(db, tenant.tenant_id, template_id)


@router.post("", status_code=201)
def create_template(
    data: RecurringInvoiceData,
    db: DatabaseSession,
    tenant: TenantUser,
):
    validate_references(db, tenant.tenant_id, data)

    try:
        template_id = db.execute(
            text("""
                INSERT INTO recurring_invoices (
                    tenant_id,
                    name, partner_id, notes,
                    xrechnung_enabled, xrechnung_buyer_reference,
                    interval_months, start_date, end_date,
                    due_days, is_active
                )
                VALUES (
                    :tenant_id,
                    :name, :partner_id, :notes,
                    :xrechnung_enabled, :xrechnung_buyer_reference,
                    :interval_months, :start_date, :end_date,
                    :due_days, :is_active
                )
                RETURNING id
            """),
            {**data.model_dump(exclude={"lines"}), "tenant_id": tenant.tenant_id},
        ).scalar_one()

        for position, line in enumerate(data.lines, start=1):
            db.execute(
                text("""
                    INSERT INTO recurring_invoice_lines (
                        tenant_id,
                        recurring_invoice_id, position,
                        product_id, quantity
                    )
                    VALUES (
                        :tenant_id, :template_id, :position,
                        :product_id, :quantity
                    )
                """),
                {
                    "tenant_id": tenant.tenant_id,
                    "template_id": template_id,
                    "position": position,
                    **line.model_dump(),
                },
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return load_template(db, tenant.tenant_id, template_id)


@router.put("/{template_id}")
def update_template(
    template_id: int,
    data: RecurringInvoiceData,
    db: DatabaseSession,
    tenant: TenantUser,
):
    validate_references(db, tenant.tenant_id, data)

    try:
        existing = db.execute(
            text("""
                SELECT id FROM recurring_invoices
                WHERE id = :id AND tenant_id = :tenant_id FOR UPDATE
            """),
            {"id": template_id, "tenant_id": tenant.tenant_id},
        ).first()

        if existing is None:
            raise HTTPException(404, "Vorlage nicht gefunden.")

        db.execute(
            text("""
                UPDATE recurring_invoices
                SET name = :name,
                    partner_id = :partner_id,
                    notes = :notes,
                    xrechnung_enabled = :xrechnung_enabled,
                    xrechnung_buyer_reference =
                        :xrechnung_buyer_reference,
                    interval_months = :interval_months,
                    start_date = :start_date,
                    end_date = :end_date,
                    due_days = :due_days,
                    is_active = :is_active,
                    updated_at = now()
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {
                "id": template_id,
                "tenant_id": tenant.tenant_id,
                **data.model_dump(exclude={"lines"}),
            },
        )

        db.execute(
            text("""
                DELETE FROM recurring_invoice_lines
                WHERE recurring_invoice_id = :id AND tenant_id = :tenant_id
            """),
            {"id": template_id, "tenant_id": tenant.tenant_id},
        )

        for position, line in enumerate(data.lines, start=1):
            db.execute(
                text("""
                    INSERT INTO recurring_invoice_lines (
                        tenant_id,
                        recurring_invoice_id, position,
                        product_id, quantity
                    )
                    VALUES (
                        :tenant_id, :template_id, :position,
                        :product_id, :quantity
                    )
                """),
                {
                    "tenant_id": tenant.tenant_id,
                    "template_id": template_id,
                    "position": position,
                    **line.model_dump(),
                },
            )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return load_template(db, tenant.tenant_id, template_id)


@router.patch("/{template_id}/active")
def set_template_active(
    template_id: int,
    data: ActiveData,
    db: DatabaseSession,
    tenant: TenantUser,
):
    result = db.execute(
        text("""
            UPDATE recurring_invoices
            SET is_active = :is_active,
                updated_at = now()
            WHERE id = :id AND tenant_id = :tenant_id
            RETURNING id
        """),
        {
            "id": template_id,
            "tenant_id": tenant.tenant_id,
            "is_active": data.is_active,
        },
    ).first()

    if result is None:
        db.rollback()
        raise HTTPException(404, "Vorlage nicht gefunden.")

    db.commit()
    return load_template(db, tenant.tenant_id, template_id)


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    db: DatabaseSession,
    tenant: TenantUser,
):
    try:
        result = db.execute(
            text("""
                DELETE FROM recurring_invoices
                WHERE id = :id AND tenant_id = :tenant_id
                RETURNING id
            """),
            {"id": template_id, "tenant_id": tenant.tenant_id},
        ).first()

        if result is None:
            raise HTTPException(404, "Vorlage nicht gefunden.")

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"deleted": True, "id": template_id}
