"""Direkte Einnahmen- und Ausgabenbuchungen je Mandant."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, TenantAdmin, TenantUser
from app.models.account import Account
from app.models.manual_booking import ManualBooking
from app.models.payment_account import PaymentAccount
from app.services.manual_booking_numbers import next_manual_booking_number


router = APIRouter(
    prefix="/api/manual-bookings",
    tags=["Manual Bookings"],
)


class ManualBookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_type: str
    booking_date: date
    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )
    payment_account_id: int = Field(gt=0)
    account_id: int = Field(gt=0)


def serialize_booking(booking: ManualBooking) -> dict:
    return {
        "id": booking.id,
        "tenant_id": booking.tenant_id,
        "booking_number": booking.booking_number,
        "booking_type": booking.booking_type,
        "booking_date": booking.booking_date,
        "amount": booking.amount,
        "payment_account_id": booking.payment_account_id,
        "account_id": booking.account_id,
        "created_at": booking.created_at,
    }


@router.get("")
def list_bookings(
    db: DatabaseSession,
    tenant: TenantUser,
):
    bookings = db.scalars(
        select(ManualBooking)
        .where(ManualBooking.tenant_id == tenant.tenant_id)
        .order_by(
            ManualBooking.booking_date.desc(),
            ManualBooking.id.desc(),
        )
    ).all()

    return [serialize_booking(item) for item in bookings]


@router.post("", status_code=201)
def create_booking(
    data: ManualBookingCreate,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    if data.booking_type not in ("income", "expense"):
        raise HTTPException(422, "Ungültige Buchungsart.")

    payment_account = db.scalar(
        select(PaymentAccount)
        .where(
            PaymentAccount.id == data.payment_account_id,
            PaymentAccount.tenant_id == tenant.tenant_id,
        )
        .with_for_update()
    )

    if payment_account is None:
        raise HTTPException(
            422, "Zahlungskonto gehört nicht zum Mandanten."
        )

    if not payment_account.is_active:
        raise HTTPException(422, "Zahlungskonto ist inaktiv.")

    if data.booking_date < payment_account.opening_date:
        raise HTTPException(
            422, "Buchungsdatum liegt vor dem Kontoanfangsdatum."
        )

    account = db.scalar(
        select(Account).where(
            Account.id == data.account_id,
            Account.tenant_id == tenant.tenant_id,
        )
    )

    if account is None:
        raise HTTPException(
            422, "Buchungskonto gehört nicht zum Mandanten."
        )

    if not account.is_active:
        raise HTTPException(422, "Buchungskonto ist inaktiv.")

    if account.account_type != data.booking_type:
        raise HTTPException(
            422, "Buchungskonto passt nicht zur Buchungsart."
        )

    number = next_manual_booking_number(
        db,
        tenant.tenant_id,
        data.booking_type,
        data.booking_date,
    )

    booking = ManualBooking(
        tenant_id=tenant.tenant_id,
        booking_number=number,
        **data.model_dump(),
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return serialize_booking(booking)
