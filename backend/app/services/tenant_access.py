from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.models.user_tenant import UserTenant


def get_accessible_tenants(db: Session, user: User):
    if user.role == UserRole.SYSTEM_ADMIN:
        return []

    statement = (
        select(Tenant, UserTenant.role)
        .join(UserTenant, UserTenant.tenant_id == Tenant.id)
        .where(
            UserTenant.user_id == user.id,
            Tenant.is_active.is_(True),
        )
        .order_by(Tenant.name)
    )
    return db.execute(statement).all()


def require_tenant_access(
    db: Session,
    user: User,
    tenant_id: int,
    admin_required: bool = False,
) -> UserTenant:
    if user.role == UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Systemadministratoren haben keinen Zugriff auf Mandantendaten.",
        )

    statement = (
        select(UserTenant)
        .join(Tenant, Tenant.id == UserTenant.tenant_id)
        .where(
            UserTenant.user_id == user.id,
            UserTenant.tenant_id == tenant_id,
            Tenant.is_active.is_(True),
        )
    )

    membership = db.scalar(statement)

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kein Zugriff auf diesen Mandanten.",
        )

    if admin_required and membership.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mandantenadministratorrechte erforderlich.",
        )

    return membership
