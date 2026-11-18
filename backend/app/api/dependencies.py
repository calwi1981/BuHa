from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.sessions import get_session_user


SESSION_COOKIE_NAME = "__Host-buha_session"

DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    request: Request,
    db: DatabaseSession,
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht angemeldet.",
        )

    user = get_session_user(db, token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sitzung ungueltig oder abgelaufen.",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(
    user: CurrentUser,
) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administratorrechte erforderlich.",
        )

    return user


AdminUser = Annotated[User, Depends(require_admin)]


# BUHA V1.2.0: Mandantenbezogene Zugriffskontrolle
from dataclasses import dataclass
from app.services.tenant_access import require_tenant_access


@dataclass(frozen=True)
class ActiveTenant:
    tenant_id: int
    user_id: int
    role: str


def get_tenant_context(
    request: Request,
    user: CurrentUser,
    db: DatabaseSession,
) -> ActiveTenant:
    raw_tenant_id = request.headers.get("X-Tenant-ID")

    if not raw_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aktiver Mandant fehlt.",
        )

    try:
        tenant_id = int(raw_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungueltige Mandanten-ID.",
        )

    if tenant_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungueltige Mandanten-ID.",
        )

    membership = require_tenant_access(db, user, tenant_id)

    return ActiveTenant(
        tenant_id=tenant_id,
        user_id=user.id,
        role=membership.role,
    )


TenantContext = Annotated[ActiveTenant, Depends(get_tenant_context)]


def require_tenant_user(
    context: TenantContext,
) -> ActiveTenant:
    return context


TenantUser = Annotated[ActiveTenant, Depends(require_tenant_user)]


def require_tenant_admin(
    context: TenantContext,
) -> ActiveTenant:
    if context.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mandantenadministratorrechte erforderlich.",
        )

    return context


TenantAdmin = Annotated[ActiveTenant, Depends(require_tenant_admin)]



# BUHA V1.2.0: Ausschliesslich globale Systemadministration
def require_system_admin(
    user: CurrentUser,
) -> User:
    if user.role != UserRole.SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Systemadministratorrechte erforderlich.",
        )

    return user


SystemAdmin = Annotated[User, Depends(require_system_admin)]
