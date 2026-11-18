from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.dependencies import DatabaseSession, TenantAdmin, TenantUser
from app.models.payment_account import PaymentAccount
from app.models.payment_account_transfer import PaymentAccountTransfer


router = APIRouter(
    prefix="/api/payment-account-transfers",
    tags=["Payment Account Transfers"],
)


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_account_id: int = Field(gt=0)
    target_account_id: int = Field(gt=0)
    transfer_date: date
    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )
    reference: str | None = Field(default=None, max_length=255)


def serialize_transfer(transfer: PaymentAccountTransfer) -> dict:
    return {
        "id": transfer.id,
        "tenant_id": transfer.tenant_id,
        "source_account_id": transfer.source_account_id,
        "target_account_id": transfer.target_account_id,
        "transfer_date": transfer.transfer_date,
        "amount": transfer.amount,
        "reference": transfer.reference,
        "created_at": transfer.created_at,
    }


@router.get("")
def list_transfers(
    db: DatabaseSession,
    tenant: TenantUser,
):
    transfers = db.scalars(
        select(PaymentAccountTransfer)
        .where(PaymentAccountTransfer.tenant_id == tenant.tenant_id)
        .order_by(
            PaymentAccountTransfer.transfer_date.desc(),
            PaymentAccountTransfer.id.desc(),
        )
    ).all()

    return [serialize_transfer(item) for item in transfers]


@router.post("", status_code=201)
def create_transfer(
    data: TransferCreate,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    if data.source_account_id == data.target_account_id:
        raise HTTPException(
            422,
            "Quellkonto und Zielkonto muessen unterschiedlich sein.",
        )

    accounts = db.scalars(
        select(PaymentAccount)
        .where(
            PaymentAccount.tenant_id == tenant.tenant_id,
            PaymentAccount.id.in_(
                [data.source_account_id, data.target_account_id]
            ),
        )
        .order_by(PaymentAccount.id)
        .with_for_update()
    ).all()

    by_id = {account.id: account for account in accounts}

    source_account = by_id.get(data.source_account_id)
    target_account = by_id.get(data.target_account_id)

    if source_account is None or target_account is None:
        raise HTTPException(
            422,
            "Quellkonto oder Zielkonto gehoert nicht zum Mandanten.",
        )

    if not source_account.is_active or not target_account.is_active:
        raise HTTPException(
            422,
            "Umbuchungen sind nur zwischen aktiven Konten erlaubt.",
        )

    if (
        data.transfer_date < source_account.opening_date
        or data.transfer_date < target_account.opening_date
    ):
        raise HTTPException(
            422,
            "Buchungsdatum liegt vor dem Anfangsdatum eines Kontos.",
        )

    transfer = PaymentAccountTransfer(
        tenant_id=tenant.tenant_id,
        **data.model_dump(),
    )

    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    return serialize_transfer(transfer)
