from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DatabaseSession, TenantAdmin, TenantUser
from app.models.payment import Payment
from app.models.payment_account import PaymentAccount
from app.models.tenant import Tenant
from app.services.payment_account_balances import list_payment_account_balances


router = APIRouter(
    prefix="/api/payment-accounts",
    tags=["Payment Accounts"],
)


class PaymentAccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    opening_balance: Decimal = Field(
        ge=Decimal("-999999999999.99"),
        le=Decimal("999999999999.99"),
        decimal_places=2,
    )
    opening_date: date
    is_default: bool = False


class PaymentAccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    opening_balance: Decimal | None = Field(
        default=None,
        ge=Decimal("-999999999999.99"),
        le=Decimal("999999999999.99"),
        decimal_places=2,
    )
    opening_date: date | None = None
    is_active: bool | None = None
    is_default: bool | None = None


def serialize_account(account: PaymentAccount):
    return {
        "id": account.id,
        "tenant_id": account.tenant_id,
        "name": account.name,
        "opening_balance": account.opening_balance,
        "opening_date": account.opening_date,
        "is_active": account.is_active,
        "is_default": account.is_default,
    }


@router.get("")
def list_payment_accounts(
    db: DatabaseSession,
    tenant: TenantUser,
):
    accounts = db.scalars(
        select(PaymentAccount)
        .where(PaymentAccount.tenant_id == tenant.tenant_id)
        .order_by(PaymentAccount.name, PaymentAccount.id)
    ).all()

    return [serialize_account(account) for account in accounts]


@router.get("/balances")
def get_payment_account_balances(
    db: DatabaseSession,
    tenant: TenantUser,
    target_date: date = Query(...),
):
    return list_payment_account_balances(
        db,
        tenant.tenant_id,
        target_date,
    )


@router.post("", status_code=201)
def create_payment_account(
    data: PaymentAccountCreate,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    name = data.name.strip()

    if not name:
        raise HTTPException(422, "Kontoname darf nicht leer sein.")

    if data.is_default:
        db.scalar(
            select(Tenant.id)
            .where(Tenant.id == tenant.tenant_id)
            .with_for_update()
        )
        db.execute(
            update(PaymentAccount)
            .where(PaymentAccount.tenant_id == tenant.tenant_id)
            .values(is_default=False)
        )

    account = PaymentAccount(
        tenant_id=tenant.tenant_id,
        name=name,
        opening_balance=data.opening_balance,
        opening_date=data.opening_date,
        is_active=True,
        is_default=data.is_default,
    )

    db.add(account)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Ein Zahlungskonto mit diesem Namen existiert bereits.",
        )

    db.refresh(account)
    return serialize_account(account)


@router.patch("/{account_id}")
def update_payment_account(
    account_id: int,
    data: PaymentAccountUpdate,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    db.scalar(
        select(Tenant.id)
        .where(Tenant.id == tenant.tenant_id)
        .with_for_update()
    )

    account = db.scalar(
        select(PaymentAccount)
        .where(
            PaymentAccount.id == account_id,
            PaymentAccount.tenant_id == tenant.tenant_id,
        )
        .with_for_update()
    )

    if account is None:
        raise HTTPException(404, "Zahlungskonto nicht gefunden.")

    changes = data.model_dump(exclude_unset=True)

    if not changes:
        return serialize_account(account)

    if "name" in changes:
        if changes["name"] is None:
            raise HTTPException(422, "Kontoname darf nicht leer sein.")
        name = changes["name"].strip()
        if not name:
            raise HTTPException(422, "Kontoname darf nicht leer sein.")
        account.name = name

    for field in ("opening_balance", "opening_date", "is_active"):
        if field in changes and changes[field] is None:
            raise HTTPException(422, f"{field} darf nicht null sein.")

    if changes.get("is_default") is True:
        if changes.get("is_active") is False or not account.is_active:
            raise HTTPException(
                422,
                "Ein inaktives Zahlungskonto kann kein Standardkonto sein.",
            )
        db.execute(
            update(PaymentAccount)
            .where(
                PaymentAccount.tenant_id == tenant.tenant_id,
                PaymentAccount.id != account.id,
            )
            .values(is_default=False)
        )

    if changes.get("is_active") is False and (
        changes.get("is_default", account.is_default) is True
    ):
        raise HTTPException(
            422,
            "Standardkonto zuerst auf ein anderes Konto umstellen.",
        )

    for field in (
        "opening_balance",
        "opening_date",
        "is_active",
        "is_default",
    ):
        if field in changes:
            setattr(account, field, changes[field])

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Zahlungskonto konnte wegen eines Datenkonflikts "
            "nicht gespeichert werden.",
        )

    db.refresh(account)
    return serialize_account(account)
