"""Einmalige BUHA-Ersteinrichtung."""

from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.bootstrap import initialize_admin


def main():
    settings = get_settings()

    if not settings.initial_admin_email:
        raise SystemExit(
            "ABBRUCH: INITIAL_ADMIN_EMAIL fehlt."
        )

    if not settings.initial_admin_password:
        raise SystemExit(
            "ABBRUCH: INITIAL_ADMIN_PASSWORD fehlt."
        )

    print("BUHA: Datenbankmigrationen starten.")

    alembic_config = Config("/app/alembic.ini")
    command.upgrade(alembic_config, "head")

    print("BUHA: Administrator-Initialisierung starten.")

    with SessionLocal() as db:
        created = initialize_admin(db)

    if created:
        print("BUHA: Erster Administrator erfolgreich angelegt.")
    else:
        print("BUHA: Benutzer vorhanden, keine Neuanlage.")

    print("BUHA: Initialisierung abgeschlossen.")


if __name__ == "__main__":
    main()
