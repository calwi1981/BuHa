import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.session import UserSession
from app.models.user import User


SESSION_DURATION_HOURS = 12


def utc_now():
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(48)
    now = utc_now()

    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        created_at=now,
        expires_at=now + timedelta(hours=SESSION_DURATION_HOURS),
        revoked_at=None,
    )

    db.add(session)
    db.commit()

    return token


def get_session_user(db: Session, token: str) -> User | None:
    if not token:
        return None

    now = utc_now()

    statement = (
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == hash_token(token),
            UserSession.expires_at > now,
            UserSession.revoked_at.is_(None),
            User.is_active.is_(True),
        )
    )

    return db.scalar(statement)


def revoke_session(db: Session, token: str) -> bool:
    if not token:
        return False

    statement = select(UserSession).where(
        UserSession.token_hash == hash_token(token),
        UserSession.revoked_at.is_(None),
    )

    session = db.scalar(statement)

    if session is None:
        return False

    session.revoked_at = utc_now()
    db.commit()

    return True
