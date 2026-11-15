from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole


def initialize_admin(db: Session) -> bool:
    existing_user = db.scalar(select(User.id).limit(1))

    if existing_user is not None:
        return False

    settings = get_settings()

    username = settings.initial_admin_username.strip()
    email = settings.initial_admin_email.strip().lower()
    password = settings.initial_admin_password

    if not username:
        raise RuntimeError("INITIAL_ADMIN_USERNAME fehlt.")

    if not email or "@" not in email:
        raise RuntimeError("INITIAL_ADMIN_EMAIL ist ungueltig.")

    if (
        len(password) < 12
        or password.startswith("CHANGE_ME")
    ):
        raise RuntimeError(
            "INITIAL_ADMIN_PASSWORD muss ein sicheres "
            "Passwort mit mindestens 12 Zeichen enthalten."
        )

    admin = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
    )

    db.add(admin)
    db.commit()

    return True
