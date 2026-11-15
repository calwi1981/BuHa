import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.recurring_processor import process_all_due


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("buha.recurring.worker")


def main():
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()

    logger.info(
        "Wiederkehrender Rechnungslauf gestartet: %s",
        today.isoformat(),
    )

    try:
        results = process_all_due(today=today)
    except Exception:
        logger.exception(
            "Wiederkehrender Rechnungslauf abgebrochen."
        )
        return 1

    successful = sum(
        1 for result in results if result.get("ok")
    )

    failed = len(results) - successful

    for result in results:
        if result.get("ok"):
            logger.info("Erfolgreich: %s", result)
        else:
            logger.error("Fehlgeschlagen: %s", result)

    logger.info(
        "Rechnungslauf abgeschlossen: %s verarbeitet, "
        "%s erfolgreich, %s fehlgeschlagen.",
        len(results),
        successful,
        failed,
    )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
