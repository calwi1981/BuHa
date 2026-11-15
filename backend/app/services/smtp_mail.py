
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from cryptography.fernet import InvalidToken


def smtp_send_buha(settings, cipher, recipient, subject, body,
                   attachment=None, filename=None,
                   extra_attachments=None):
    host = str(settings.get("smtp_host") or "").strip()
    port = int(settings.get("smtp_port") or 587)
    security = settings.get("smtp_security") or "starttls"
    username = str(settings.get("smtp_username") or "").strip()
    sender = str(settings.get("smtp_from_email") or "").strip()
    sender_name = str(settings.get("smtp_from_name") or "").strip()
    encrypted = settings.get("smtp_password_encrypted")

    if not host or not sender:
        raise ValueError("SMTP-Server oder Absenderadresse fehlt.")

    if security not in {"starttls", "ssl", "none"}:
        raise ValueError("Ungültige SMTP-Verschlüsselung.")

    password = None
    if encrypted:
        try:
            password = cipher.decrypt(
                encrypted.encode("ascii")
            ).decode("utf-8")
        except InvalidToken:
            raise ValueError("SMTP-Passwort kann nicht entschlüsselt werden.")

    message = EmailMessage()
    message["From"] = formataddr((sender_name, sender))
    message["To"] = recipient
    message["Subject"] = subject

    reply_to = str(settings.get("smtp_reply_to") or "").strip()
    if reply_to:
        message["Reply-To"] = reply_to

    bcc = ""
    if settings.get("invoice_bcc_enabled"):
        bcc = str(settings.get("invoice_bcc_email") or "").strip()

    message.set_content(body)

    if attachment is not None:
        message.add_attachment(
            attachment,
            maintype="application",
            subtype="pdf",
            filename=filename or "Rechnung.pdf",
        )

    if extra_attachments:
        for item in extra_attachments:
            if not isinstance(item, dict):
                raise ValueError("Ungueltiger E-Mail-Anhang.")

            content = item.get("content")
            attachment_name = item.get("filename")
            subtype = item.get("subtype", "xml")

            if not isinstance(content, bytes) or not content:
                raise ValueError("Anhang muss binaere Daten enthalten.")

            if not isinstance(attachment_name, str) or not attachment_name:
                raise ValueError("Anhang-Dateiname fehlt.")

            if subtype not in {"xml", "pdf"}:
                raise ValueError("Nicht unterstuetzter Anhangstyp.")

            message.add_attachment(
                content,
                maintype="application",
                subtype=subtype,
                filename=attachment_name,
            )

    recipients = [recipient]
    if bcc:
        recipients.append(bcc)

    context = ssl.create_default_context()

    if security == "ssl":
        smtp = smtplib.SMTP_SSL(
            host, port, timeout=20, context=context
        )
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)

    with smtp:
        smtp.ehlo()

        if security == "starttls":
            smtp.starttls(context=context)
            smtp.ehlo()

        if username:
            if security == "none":
                raise ValueError(
                    "SMTP-Anmeldung ohne TLS ist nicht zulässig."
                )
            if not password:
                raise ValueError("SMTP-Passwort fehlt.")
            smtp.login(username, password)

        smtp.send_message(
            message,
            from_addr=sender,
            to_addrs=recipients,
        )

    return True
