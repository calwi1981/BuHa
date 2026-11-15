from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.models.login_attempt import LoginAttempt


MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def utc_now():
    return datetime.now(timezone.utc)


def normalize_username(username: str) -> str:
    return username.strip().casefold()


def acquire_login_lock(db: Session, username: str) -> None:
    db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended(:username, 0)"
            ")"
        ),
        {"username": "buha-login:" + username},
    )


def failed_attempt_count(
    db: Session,
    username: str,
    now: datetime,
) -> int:
    cutoff = now - timedelta(minutes=LOCKOUT_MINUTES)

    statement = select(func.count(LoginAttempt.id)).where(
        LoginAttempt.username == username,
        LoginAttempt.attempted_at > cutoff,
    )

    return db.scalar(statement) or 0


def is_login_blocked(
    db: Session,
    username: str,
    now: datetime | None = None,
) -> bool:
    username = normalize_username(username)
    now = now or utc_now()

    return failed_attempt_count(
        db,
        username,
        now,
    ) >= MAX_FAILED_ATTEMPTS


def record_failed_login(
    db: Session,
    username: str,
    now: datetime | None = None,
) -> None:
    username = normalize_username(username)
    now = now or utc_now()

    db.add(
        LoginAttempt(
            username=username,
            attempted_at=now,
        )
    )

    db.flush()


def clear_failed_logins(
    db: Session,
    username: str,
) -> None:
    username = normalize_username(username)

    db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.username == username
        )
    )


def cleanup_old_attempts(
    db: Session,
    now: datetime | None = None,
) -> int:
    now = now or utc_now()
    cutoff = now - timedelta(minutes=LOCKOUT_MINUTES)

    result = db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.attempted_at <= cutoff
        )
    )

    return result.rowcount
