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
