from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import TenantUser, DatabaseSession
from app.models.account import Account

router = APIRouter(prefix="/api/accounts", tags=["Kontenplan"])

ACCOUNT_TYPES = {"income", "expense", "asset", "liability", "equity"}
TAX_TREATMENTS = {"output_vat", "input_vat", "none"}


class AccountData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=255)
    account_type: str
    description: str | None = None
    is_active: bool = True

    default_vat_rate: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, decimal_places=2
    )
    tax_treatment: str = "none"
    input_vat_deductible_percent: Decimal = Field(
        default=Decimal("100"), ge=0, le=100, decimal_places=2
    )


def serialize(item):
    return {
        column.name: getattr(item, column.name)
        for column in item.__table__.columns
    }


@router.get("")
def list_accounts(db: DatabaseSession, user: TenantUser):
    items = db.scalars(
        select(Account).where(Account.tenant_id == user.tenant_id).order_by(Account.number)
    ).all()
    return [serialize(item) for item in items]


@router.get("/{item_id}")
def get_account(item_id: int, db: DatabaseSession, user: TenantUser):
    item = db.scalar(select(Account).where(Account.id == item_id, Account.tenant_id == user.tenant_id))
    if item is None:
        raise HTTPException(404, "Konto nicht gefunden.")
    return serialize(item)


@router.post("", status_code=201)
def create_account(data: AccountData, db: DatabaseSession, user: TenantUser):
    if data.tax_treatment not in TAX_TREATMENTS:
        raise HTTPException(422, "Ungueltige Steuerbehandlung.")
    if data.account_type == "income" and data.tax_treatment == "input_vat":
        raise HTTPException(422, "Einnahmekonto mit Vorsteuer unzulaessig.")
    if data.account_type == "expense" and data.tax_treatment == "output_vat":
        raise HTTPException(422, "Ausgabekonto mit Umsatzsteuer unzulaessig.")
    if data.account_type not in ACCOUNT_TYPES:
        raise HTTPException(422, "Ungueltige Kontoart.")

    item = Account(tenant_id=user.tenant_id, **data.model_dump())
    db.add(item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Kontonummer bereits vorhanden.")

    db.refresh(item)
    return serialize(item)


@router.put("/{item_id}")
def update_account(
    item_id: int,
    data: AccountData,
    db: DatabaseSession,
    user: TenantUser,
):
    if data.tax_treatment not in TAX_TREATMENTS:
        raise HTTPException(422, "Ungueltige Steuerbehandlung.")
    if data.account_type == "income" and data.tax_treatment == "input_vat":
        raise HTTPException(422, "Einnahmekonto mit Vorsteuer unzulaessig.")
    if data.account_type == "expense" and data.tax_treatment == "output_vat":
        raise HTTPException(422, "Ausgabekonto mit Umsatzsteuer unzulaessig.")
    if data.account_type not in ACCOUNT_TYPES:
        raise HTTPException(422, "Ungueltige Kontoart.")

    item = db.scalar(select(Account).where(Account.id == item_id, Account.tenant_id == user.tenant_id))
    if item is None:
        raise HTTPException(404, "Konto nicht gefunden.")

    for key, value in data.model_dump().items():
        setattr(item, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Kontonummer bereits vorhanden.")

    db.refresh(item)
    return serialize(item)
