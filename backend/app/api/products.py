from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import TenantUser, DatabaseSession
from app.models.account import Account
from app.models.product import Product

router = APIRouter(prefix="/api/products", tags=["Produkte"])


class ProductData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    product_type: str = "service"
    unit: str = "Stueck"
    net_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    revenue_account_id: int | None = None
    is_active: bool = True


def serialize(item):
    return {
        column.name: getattr(item, column.name)
        for column in item.__table__.columns
    }


def validate_product(data, db, tenant_id):
    if data.product_type not in {"product", "service"}:
        raise HTTPException(422, "Ungueltiger Produkttyp.")

    if data.revenue_account_id is not None:
        account = db.scalar(select(Account).where(Account.id == data.revenue_account_id, Account.tenant_id == tenant_id))
        if account is None or not account.is_active:
            raise HTTPException(422, "Buchungskonto nicht vorhanden oder inaktiv.")
        if account.account_type not in {"income", "expense"}:
            raise HTTPException(422, "Das Konto muss ein Einnahmen- oder Ausgabenkonto sein.")


@router.get("")
def list_products(db: DatabaseSession, user: TenantUser):
    items = db.scalars(
        select(Product).where(Product.tenant_id == user.tenant_id).order_by(Product.name, Product.id)
    ).all()
    return [serialize(item) for item in items]


@router.get("/{item_id}")
def get_product(item_id: int, db: DatabaseSession, user: TenantUser):
    item = db.scalar(select(Product).where(Product.id == item_id, Product.tenant_id == user.tenant_id))
    if item is None:
        raise HTTPException(404, "Produkt nicht gefunden.")
    return serialize(item)


@router.post("", status_code=201)
def create_product(data: ProductData, db: DatabaseSession, user: TenantUser):
    validate_product(data, db, user.tenant_id)

    values = data.model_dump()
    if data.revenue_account_id is not None:
        account = db.scalar(select(Account).where(Account.id == data.revenue_account_id, Account.tenant_id == user.tenant_id))
        values["vat_rate"] = account.default_vat_rate
    else:
        values["vat_rate"] = Decimal("0")
    item = Product(tenant_id=user.tenant_id, **values)
    db.add(item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Artikelnummer bereits vorhanden.")

    db.refresh(item)
    return serialize(item)


@router.put("/{item_id}")
def update_product(
    item_id: int,
    data: ProductData,
    db: DatabaseSession,
    user: TenantUser,
):
    item = db.scalar(select(Product).where(Product.id == item_id, Product.tenant_id == user.tenant_id))
    if item is None:
        raise HTTPException(404, "Produkt nicht gefunden.")

    validate_product(data, db, user.tenant_id)

    values = data.model_dump()
    if data.revenue_account_id is not None:
        account = db.scalar(select(Account).where(Account.id == data.revenue_account_id, Account.tenant_id == user.tenant_id))
        values["vat_rate"] = account.default_vat_rate
    else:
        values["vat_rate"] = item.vat_rate
    for key, value in values.items():
        setattr(item, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Artikelnummer bereits vorhanden.")

    db.refresh(item)
    return serialize(item)
