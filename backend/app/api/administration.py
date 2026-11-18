
import base64
import binascii
from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.api.dependencies import DatabaseSession, TenantAdmin, TenantUser

router = APIRouter(prefix="/api/administration", tags=["Administration"])

FIELDS = {
    "invoice_bcc_enabled",
    "invoice_bcc_email",
    "company_name",
    "company_additional",
    "street",
    "postal_code",
    "city",
    "country",
    "phone",
    "fax",
    "email",
    "website",
    "tax_number",
    "vat_id",
    "bank_name",
    "bank_holder",
    "iban",
    "bic",
    "invoice_footer",
    "invoice_prefix",
    "incoming_prefix",
    "invoice_digits",
    "incoming_digits",
    "invoice_next",
    "incoming_next",
    "booking_income_prefix",
    "booking_income_digits",
    "booking_income_next",
    "booking_expense_prefix",
    "booking_expense_digits",
    "booking_expense_next",
    "utility_invoice_prefix",
    "utility_invoice_digits",
    "utility_invoice_next",

    "bank_opening_balance",
    "bank_opening_date",
}

DEFAULTS = {
    "invoice_bcc_enabled": False,
    "invoice_bcc_email": "",
    "company_name": "",
    "company_additional": "",
    "street": "",
    "postal_code": "",
    "city": "",
    "country": "DE",
    "phone": "",
    "fax": "",
    "email": "",
    "website": "",
    "tax_number": "",
    "vat_id": "",
    "bank_name": "",
    "bank_holder": "",
    "iban": "",
    "bic": "",
    "invoice_footer": "",
    "invoice_prefix": "RE",
    "incoming_prefix": "LR",
    "invoice_digits": 4,
    "incoming_digits": 4,
    "invoice_next": 1,
    "incoming_next": 1,
    "booking_income_prefix": "E",
    "booking_income_digits": 4,
    "booking_income_next": 1,
    "booking_expense_prefix": "A",
    "booking_expense_digits": 4,
    "booking_expense_next": 1,
    "utility_invoice_prefix": "NK",
    "utility_invoice_digits": 1,
    "utility_invoice_next": 1,

    "bank_opening_balance": "0.00",
    "bank_opening_date": "",
}


def validate_invoice_bcc_settings(values):
    from email_validator import validate_email, EmailNotValidError

    enabled = values.get("invoice_bcc_enabled", False)
    address = values.get("invoice_bcc_email", "")

    if not isinstance(enabled, bool):
        raise HTTPException(
            status_code=422,
            detail="BCC-Aktivierung muss wahr oder falsch sein.",
        )

    if not isinstance(address, str):
        raise HTTPException(
            status_code=422,
            detail="BCC-Adresse muss Text sein.",
        )

    address = address.strip()

    if address:
        try:
            result = validate_email(
                address,
                check_deliverability=False,
            )
            address = result.normalized
        except EmailNotValidError:
            raise HTTPException(
                status_code=422,
                detail="Ungueltige BCC-E-Mail-Adresse.",
            )

    if enabled and not address:
        raise HTTPException(
            status_code=422,
            detail="Bei aktiver BCC-Kopie ist eine E-Mail-Adresse erforderlich.",
        )

    values["invoice_bcc_enabled"] = enabled
    values["invoice_bcc_email"] = address
    return values


class SettingsData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict


class LogoData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_base64: str = Field(max_length=3000000)
    mime: str



# BUHA_AUTO_SEND_163
FIELDS.add("invoice_auto_send_enabled")
DEFAULTS["invoice_auto_send_enabled"] = False

# SMTP_FIELDS_BUHA
SMTP_FIELDS_BUHA = {
    "smtp_host", "smtp_port", "smtp_security",
    "smtp_username", "smtp_from_name",
    "smtp_from_email", "smtp_reply_to",
    "invoice_mail_subject", "invoice_mail_body",
}

SMTP_DEFAULTS_BUHA = {
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_security": "starttls",
    "smtp_username": "",
    "smtp_from_name": "",
    "smtp_from_email": "",
    "smtp_reply_to": "",
    "invoice_mail_subject": "Ihre Rechnung {rechnungsnummer}",
    "invoice_mail_body": (
        "Guten Tag,\\n\\n"
        "anbei erhalten Sie unsere Rechnung {rechnungsnummer} "
        "vom {rechnungsdatum} über {bruttobetrag} "
        "als PDF-Anhang.\\n\\n"
        "Mit freundlichen Grüßen\\n{firmenname}"
    ),
}

FIELDS.update(SMTP_FIELDS_BUHA)
DEFAULTS.update(SMTP_DEFAULTS_BUHA)


def smtp_public_settings(values):
    return {
        key: value for key, value in values.items()
        if key != "smtp_password_encrypted"
    }


def smtp_validate_settings(values):
    from email_validator import validate_email, EmailNotValidError

    security = values.get("smtp_security", "starttls")
    if security not in {"starttls", "ssl", "none"}:
        raise HTTPException(422, "Ungültige SMTP-Verschlüsselung.")

    try:
        port = int(values.get("smtp_port", 587))
    except (TypeError, ValueError):
        raise HTTPException(422, "Ungültiger SMTP-Port.")

    if not 1 <= port <= 65535:
        raise HTTPException(422, "SMTP-Port außerhalb des gültigen Bereichs.")

    values["smtp_port"] = str(port)

    for key in ("smtp_from_email", "smtp_reply_to"):
        address = values.get(key, "")
        if address:
            try:
                values[key] = validate_email(
                    address, check_deliverability=False
                ).normalized
            except EmailNotValidError:
                raise HTTPException(422, "Ungültige SMTP-E-Mail-Adresse.")

    return values

def load_settings(db, tenant_id: int):
    if not isinstance(tenant_id, int) or tenant_id <= 0:
        raise ValueError("Gueltige Mandanten-ID erforderlich.")

    row = db.execute(
        text(
            "SELECT settings FROM company_settings "
            "WHERE tenant_id=:tenant_id"
        ),
        {"tenant_id": tenant_id},
    ).scalar_one_or_none()

    if row is None:
        raise ValueError("Mandanteneinstellungen nicht vorhanden.")

    return {**DEFAULTS, **row}


@router.get("")
def get_settings(db: DatabaseSession, tenant: TenantAdmin):
    settings = load_settings(db, tenant.tenant_id)
    has_logo = db.execute(
        text(
            "SELECT logo IS NOT NULL FROM company_settings "
            "WHERE tenant_id=:tenant_id"
        ),
        {"tenant_id": tenant.tenant_id},
    ).scalar_one()
    return {"values": smtp_public_settings(settings), "has_logo": has_logo}


@router.put("")
def save_settings(
    data: SettingsData,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    unknown = set(data.values) - FIELDS
    if unknown:
        raise HTTPException(422, "Unbekannte Einstellungen.")

    db.execute(
        text("SELECT pg_advisory_xact_lock(127001)")
    )

    settings = load_settings(db, tenant.tenant_id)

    for key, value in data.values.items():
        if key in {
            "invoice_digits", "incoming_digits",
            "booking_income_digits",
            "booking_expense_digits",
            "utility_invoice_digits",
            "invoice_next", "incoming_next",
            "booking_income_next",
            "booking_expense_next",
            "utility_invoice_next",
        }:
            if isinstance(value, bool):
                raise HTTPException(422, "Ungültiger Zahlenwert.")
            try:
                value = int(value)
            except (TypeError, ValueError):
                raise HTTPException(422, "Ungültiger Zahlenwert.")

            if key == "utility_invoice_digits":
                if not 1 <= value <= 8:
                    raise HTTPException(422, "NK-Stellenzahl muss 1 bis 8 sein.")
            elif key.endswith("_digits") and not 3 <= value <= 8:
                raise HTTPException(422, "Stellenzahl muss 3 bis 8 sein.")

            if key.endswith("_next") and value < 1:
                raise HTTPException(422, "Startnummer muss positiv sein.")
        elif key in {"invoice_bcc_enabled", "invoice_auto_send_enabled"}:
            if isinstance(value, bool):
                pass
            elif isinstance(value, str) and value.lower() in {
                "true", "false", "on", "off"
            }:
                value = value.lower() in {"true", "on"}
            else:
                raise HTTPException(422, "Ungültiger BCC-Status.")
        else:
            if not isinstance(value, str) or len(value) > 2000:
                raise HTTPException(422, "Ungültiger Textwert.")
            value = value.strip()

        if key == "bank_opening_balance":
            from decimal import Decimal, InvalidOperation
            try:
                amount = Decimal(str(value).replace(",", "."))
                if not amount.is_finite():
                    raise InvalidOperation
                value = str(amount.quantize(Decimal("0.01")))
            except (InvalidOperation, ValueError):
                raise HTTPException(
                    422, "Ungültiger Bankanfangsbestand."
                )

        if key == "bank_opening_date" and value:
            from datetime import date
            try:
                value = date.fromisoformat(value).isoformat()
            except ValueError:
                raise HTTPException(
                    422, "Bankstichtag muss JJJJ-MM-TT sein."
                )

        if key in {"invoice_prefix", "incoming_prefix", "utility_invoice_prefix", "booking_income_prefix", "booking_expense_prefix"}:
            if not value.isalpha() or not 1 <= len(value) <= 8:
                raise HTTPException(422, "Präfix muss aus Buchstaben bestehen.")
            value = value.upper()

        settings[key] = value

    settings = smtp_validate_settings(settings)
    settings = validate_invoice_bcc_settings(settings)

    import json

    db.execute(
        text("""
            UPDATE company_settings
            SET settings=CAST(:settings AS jsonb)
            WHERE tenant_id=:tenant_id
        """),
        {"settings": json.dumps(settings), "tenant_id": tenant.tenant_id},
    )
    db.commit()
    return {"values": smtp_public_settings(settings)}


@router.put("/logo")
def upload_logo(
    data: LogoData,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    if data.mime not in {"image/png", "image/jpeg"}:
        raise HTTPException(422, "Nur PNG oder JPEG erlaubt.")

    try:
        content = base64.b64decode(
            data.content_base64, validate=True
        )
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Ungültige Bilddaten.")

    if not content or len(content) > 2_000_000:
        raise HTTPException(422, "Logo darf maximal 2 MB groß sein.")

    try:
        from PIL import Image
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"PNG", "JPEG"}:
                raise ValueError("Format")
            if image.width > 4000 or image.height > 4000:
                raise ValueError("Abmessungen")
            actual = (
                "image/png" if image.format == "PNG"
                else "image/jpeg"
            )
    except Exception:
        raise HTTPException(422, "Bilddatei ungültig.")

    if actual != data.mime:
        raise HTTPException(422, "Dateityp stimmt nicht überein.")

    db.execute(
        text("""
            UPDATE company_settings
            SET logo=:logo, logo_mime=:mime
            WHERE tenant_id=:tenant_id
        """),
        {"logo": content, "mime": actual, "tenant_id": tenant.tenant_id},
    )
    db.commit()
    return {"ok": True}


@router.get("/logo")
def get_logo(db: DatabaseSession, tenant: TenantUser):
    row = db.execute(
        text("""
            SELECT logo, logo_mime
            FROM company_settings WHERE tenant_id=:tenant_id
        """),
        {"tenant_id": tenant.tenant_id},
    ).one_or_none()

    if not row or row.logo is None:
        raise HTTPException(404, "Kein Logo hinterlegt.")

    return Response(
        content=bytes(row.logo),
        media_type=row.logo_mime,
        headers={"Cache-Control": "private, no-store"},
    )


# BUHA SMTP credential management
from pydantic import BaseModel as SMTPBaseModel


class SMTPPasswordDataBUHA(SMTPBaseModel):
    password: str


def smtp_cipher_buha():
    import os
    from cryptography.fernet import Fernet

    key = os.environ.get("BUHA_SMTP_ENCRYPTION_KEY", "")
    if not key:
        raise HTTPException(
            status_code=503,
            detail="SMTP-Verschlüsselungsschlüssel fehlt im App-Container.",
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=503,
            detail="SMTP-Verschlüsselungsschlüssel ist ungültig.",
        )


@router.put("/smtp/password")
def save_smtp_password_buha(
    data: SMTPPasswordDataBUHA,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    import json

    password = data.password
    if not isinstance(password, str) or len(password) > 1024:
        raise HTTPException(422, "Ungültiges SMTP-Passwort.")

    db.execute(text("SELECT pg_advisory_xact_lock(127001)"))
    settings = load_settings(db, tenant.tenant_id)

    if password:
        encrypted = smtp_cipher_buha().encrypt(
            password.encode("utf-8")
        ).decode("ascii")
        settings["smtp_password_encrypted"] = encrypted
    else:
        settings.pop("smtp_password_encrypted", None)

    db.execute(
        text("""
            UPDATE company_settings
            SET settings=CAST(:settings AS jsonb)
            WHERE tenant_id=:tenant_id
        """),
        {"settings": json.dumps(settings), "tenant_id": tenant.tenant_id},
    )
    db.commit()
    return {"ok": True, "password_configured": bool(password)}


@router.get("/smtp/status")
def smtp_password_status_buha(
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    settings = load_settings(db, tenant.tenant_id)
    return {
        "password_configured": bool(
            settings.get("smtp_password_encrypted")
        )
    }


from app.services.smtp_mail import smtp_send_buha


class SMTPTestDataBUHA(SMTPBaseModel):
    recipient: str


@router.post("/smtp/test")
def send_smtp_test_buha(
    data: SMTPTestDataBUHA,
    db: DatabaseSession,
    tenant: TenantAdmin,
):
    from email_validator import validate_email, EmailNotValidError

    try:
        recipient = validate_email(
            data.recipient,
            check_deliverability=False,
        ).normalized
    except EmailNotValidError:
        raise HTTPException(422, "Ungültige Test-E-Mail-Adresse.")

    settings = load_settings(db, tenant.tenant_id)

    try:
        smtp_send_buha(
            settings=settings,
            cipher=smtp_cipher_buha(),
            recipient=recipient,
            subject="BUHA – SMTP-Test",
            body="Der SMTP-Versand aus BUHA funktioniert.",
        )
    except Exception:
        raise HTTPException(
            502,
            "SMTP-Test fehlgeschlagen. Bitte Einstellungen prüfen.",
        )

    return {"ok": True}
