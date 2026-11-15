from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.dependencies import (
    CurrentUser,
    DatabaseSession,
    SESSION_COOKIE_NAME,
)
from app.core.security import verify_password
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserResponse,
)
from app.services.login_protection import (
    acquire_login_lock,
    clear_failed_logins,
    is_login_blocked,
    normalize_username,
    record_failed_login,
)
from app.services.sessions import (
    SESSION_DURATION_HOURS,
    create_session,
    revoke_session,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentifizierung"],
)


def serialize_user(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
    response: Response,
    db: DatabaseSession,
):
    username = normalize_username(data.username)

    acquire_login_lock(db, username)

    if is_login_blocked(db, username):
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele Anmeldeversuche. Bitte spaeter erneut versuchen.",
            headers={"Retry-After": "900"},
        )

    user = db.scalar(
        select(User).where(User.username == username)
    )

    valid = (
        user is not None
        and user.is_active
        and verify_password(data.password, user.password_hash)
    )

    if not valid:
        record_failed_login(db, username)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort ungueltig.",
        )

    clear_failed_logins(db, username)

    token = create_session(db, user)

    user.last_login_at = datetime.now(timezone.utc)

    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_DURATION_HOURS * 3600,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )

    return LoginResponse(
        message="Anmeldung erfolgreich.",
        user=serialize_user(user),
    )


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    db: DatabaseSession,
):
    token = request.cookies.get(SESSION_COOKIE_NAME)

    if token:
        revoke_session(db, token)

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )

    return LogoutResponse(
        message="Abmeldung erfolgreich.",
    )


@router.get("/me", response_model=UserResponse)
def current_user(user: CurrentUser):
    return serialize_user(user)
