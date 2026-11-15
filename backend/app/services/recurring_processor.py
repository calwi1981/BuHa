"""Verarbeitung wiederkehrender Rechnungen.

Aufruf nur durch den spaeteren Scheduler.
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, text

from app.core.database import SessionLocal
from app.models.invoice import Invoice
from app.services.recurring_schedule import due_occurrences
from app.services.recurring_generator import create_recurring_draft
from app.services.invoice_email import deliver_invoice_email
from app.api.invoices import finalize_invoice_core

logger = logging.getLogger("buha.recurring")


def process_recurring_invoice(template_id, scheduled_date):
    """Erstellt und versendet eine wiederkehrende Rechnung."""

    with SessionLocal() as db:
        try:
            result = create_recurring_draft(
                db,
                template_id,
                scheduled_date,
            )
            db.commit()
        except Exception as error:
            db.rollback()
            logger.exception(
                "Rechnungserstellung fehlgeschlagen: Vorlage=%s Termin=%s",
                template_id,
                scheduled_date,
            )
            return {
                "ok": False,
                "template_id": template_id,
                "scheduled_date": str(scheduled_date),
                "error": str(error),
            }

        invoice_id = result["invoice_id"]
        run_id = result["run_id"]

        if invoice_id is None:
            return {
                "ok": False,
                "run_id": run_id,
                "error": "Keine Rechnung zugeordnet.",
            }

        invoice = db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .with_for_update()
        ).scalar_one()

        if invoice.status == "draft":
            try:
                finalize_invoice_core(db, invoice)

                db.execute(
                    text("""
                        UPDATE recurring_invoice_runs
                        SET status = 'created',
                            completed_at = now(),
                            error_message = NULL
                        WHERE id = :id
                    """),
                    {"id": run_id},
                )

                db.commit()

            except Exception as error:
                db.rollback()
                logger.exception(
                    "Rechnungsfreigabe fehlgeschlagen: Lauf=%s Rechnung=%s",
                    run_id,
                    invoice_id,
                )
                return {
                    "ok": False,
                    "run_id": run_id,
                    "invoice_id": invoice_id,
                    "error": str(error),
                }
        else:
            db.rollback()

        current_invoice_status = db.execute(
            select(Invoice.status)
            .where(Invoice.id == invoice_id)
        ).scalar_one()

        if current_invoice_status not in ("open", "partial", "paid"):
            logger.error(
                "Versand gesperrt: Lauf=%s Rechnung=%s Status=%s",
                run_id,
                invoice_id,
                current_invoice_status,
            )
            db.rollback()
            return {
                "ok": False,
                "run_id": run_id,
                "invoice_id": invoice_id,
                "error": (
                    "Rechnungsstatus erlaubt keinen Versand: "
                    + str(current_invoice_status)
                ),
            }

        status = db.execute(
            text("""
                SELECT email_status
                FROM recurring_invoice_runs
                WHERE id = :id
            """),
            {"id": run_id},
        ).scalar_one()

        if status in ("sent", "sending", "failed"):
            return {
                "ok": status == "sent",
                "run_id": run_id,
                "invoice_id": invoice_id,
                "email_status": status,
                "already_processed": True,
            }

        claimed = db.execute(
            text("""
                UPDATE recurring_invoice_runs
                SET email_status = 'sending'
                WHERE id = :id
                  AND email_status = 'pending'
                RETURNING id
            """),
            {"id": run_id},
        ).scalar_one_or_none()

        db.commit()

        if claimed is None:
            return {
                "ok": False,
                "run_id": run_id,
                "invoice_id": invoice_id,
                "error": "Versand bereits beansprucht oder abgeschlossen.",
            }

        try:
            delivery = deliver_invoice_email(
                db,
                invoice_id,
                delivery_type="automatic",
            )
        except Exception as error:
            db.rollback()
            logger.exception(
                "E-Mail-Versand fehlgeschlagen: Lauf=%s Rechnung=%s",
                run_id,
                invoice_id,
            )

            db.execute(
                text("""
                    UPDATE recurring_invoice_runs
                    SET email_status = 'failed',
                        email_error = :error
                    WHERE id = :id
                """),
                {
                    "id": run_id,
                    "error": str(error),
                },
            )
            db.commit()

            return {
                "ok": False,
                "run_id": run_id,
                "invoice_id": invoice_id,
                "email_status": "failed",
                "error": str(error),
            }

        if not delivery["ok"]:
            logger.error(
                "Rechnungsversand fehlgeschlagen: Lauf=%s Rechnung=%s Fehler=%s",
                run_id,
                invoice_id,
                delivery.get("error", "Unbekannter Fehler"),
            )

        if delivery["ok"]:
            db.execute(
                text("""
                    UPDATE recurring_invoice_runs
                    SET email_status = 'sent',
                        email_error = NULL,
                        email_sent_at = now()
                    WHERE id = :id
                """),
                {"id": run_id},
            )
        else:
            db.execute(
                text("""
                    UPDATE recurring_invoice_runs
                    SET email_status = 'failed',
                        email_error = :error
                    WHERE id = :id
                """),
                {
                    "id": run_id,
                    "error": delivery.get("error"),
                },
            )

        db.commit()

        return {
            "ok": delivery["ok"],
            "run_id": run_id,
            "invoice_id": invoice_id,
            "email_status": (
                "sent" if delivery["ok"] else "failed"
            ),
        }


def process_all_due(today=None):
    """Verarbeitet alle faelligen aktiven Vorlagen."""

    today = today or datetime.now(ZoneInfo("Europe/Berlin")).date()
    results = []

    with SessionLocal() as db:
        templates = db.execute(
            text("""
                SELECT id, start_date, end_date, interval_months
                FROM recurring_invoices
                WHERE is_active = true
                ORDER BY id
            """)
        ).mappings().all()

        schedules = []

        for template in templates:
            last_date = db.execute(
                text("""
                    SELECT max(scheduled_date)
                    FROM recurring_invoice_runs
                    WHERE recurring_invoice_id = :id
                      AND invoice_id IS NOT NULL
                """),
                {"id": template["id"]},
            ).scalar_one()

            unfinished = db.execute(
                text("""
                    SELECT r.scheduled_date
                    FROM recurring_invoice_runs r
                    JOIN invoices i ON i.id = r.invoice_id
                    WHERE r.recurring_invoice_id = :id
                      AND r.scheduled_date <= :today
                      AND i.status = 'draft'
                    ORDER BY r.scheduled_date
                """),
                {
                    "id": template["id"],
                    "today": today,
                },
            ).scalars().all()

            for scheduled_date in unfinished:
                schedules.append(
                    (template["id"], scheduled_date)
                )

            pending_delivery = db.execute(
                text("""
                    SELECT r.scheduled_date
                    FROM recurring_invoice_runs r
                    JOIN invoices i ON i.id = r.invoice_id
                    WHERE r.recurring_invoice_id = :id
                      AND r.scheduled_date <= :today
                      AND r.email_status = 'pending'
                      AND i.status IN ('open', 'partial', 'paid')
                    ORDER BY r.scheduled_date
                """),
                {
                    "id": template["id"],
                    "today": today,
                },
            ).scalars().all()

            for scheduled_date in pending_delivery:
                schedules.append(
                    (template["id"], scheduled_date)
                )

            dates = due_occurrences(
                start_date=template["start_date"],
                interval_months=template["interval_months"],
                today=today,
                last_occurrence=last_date,
                end_date=template["end_date"],
            )

            for scheduled_date in dates:
                schedules.append(
                    (template["id"], scheduled_date)
                )

    processed = set()

    for template_id, scheduled_date in schedules:
        key = (template_id, scheduled_date)

        if key in processed:
            continue

        processed.add(key)

        results.append(
            process_recurring_invoice(
                template_id,
                scheduled_date,
            )
        )

    return results
