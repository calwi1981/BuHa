from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentUser, DatabaseSession
from app.models.partner import Partner

router = APIRouter(prefix="/api/partners", tags=["Partner"])


class PartnerData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partner_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    is_customer: bool = False
    is_supplier: bool = False
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str = Field(default="DE", min_length=2, max_length=2)
    email: str | None = None
    phone: str | None = None
    vat_id: str | None = None
    xrechnung_endpoint: str | None = Field(default=None, max_length=320)
    xrechnung_endpoint_scheme: str | None = Field(default=None, max_length=10)
    xrechnung_buyer_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    is_active: bool = True


def serialize(item):
    return {
        column.name: getattr(item, column.name)
        for column in item.__table__.columns
    }


@router.get("")
def list_partners(db: DatabaseSession, user: CurrentUser):
    items = db.scalars(
        select(Partner).order_by(Partner.name, Partner.id)
    ).all()
    return [serialize(item) for item in items]


@router.get("/{item_id}")
def get_partner(item_id: int, db: DatabaseSession, user: CurrentUser):
    item = db.get(Partner, item_id)
    if item is None:
        raise HTTPException(404, "Partner nicht gefunden.")
    return serialize(item)


@router.post("", status_code=201)
def create_partner(data: PartnerData, db: DatabaseSession, user: CurrentUser):
    if not data.is_customer and not data.is_supplier:
        raise HTTPException(422, "Kunde oder Lieferant muss aktiviert sein.")

    item = Partner(**data.model_dump())
    db.add(item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Partnernummer bereits vorhanden.")

    db.refresh(item)
    return serialize(item)


@router.put("/{item_id}")
def update_partner(
    item_id: int,
    data: PartnerData,
    db: DatabaseSession,
    user: CurrentUser,
):
    item = db.get(Partner, item_id)
    if item is None:
        raise HTTPException(404, "Partner nicht gefunden.")

    if not data.is_customer and not data.is_supplier:
        raise HTTPException(422, "Kunde oder Lieferant muss aktiviert sein.")

    for key, value in data.model_dump().items():
        setattr(item, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Partnernummer bereits vorhanden.")

    db.refresh(item)
    return serialize(item)
