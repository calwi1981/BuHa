"""Terminberechnung fuer wiederkehrende BUHA-Rechnungen."""

from calendar import monthrange
from datetime import date


def occurrence_date(start_date: date, interval_months: int, index: int) -> date:
    """Berechnet einen Termin relativ zum urspruenglichen Startdatum."""
    if interval_months < 1:
        raise ValueError("Das Monatsintervall muss mindestens 1 betragen.")

    if index < 0:
        raise ValueError("Der Terminindex darf nicht negativ sein.")

    start_month = start_date.year * 12 + start_date.month - 1
    target_month = start_month + index * interval_months

    year, month_zero = divmod(target_month, 12)
    month = month_zero + 1

    day = min(start_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def next_occurrence(
    start_date: date,
    interval_months: int,
    after_date: date | None = None,
    end_date: date | None = None,
) -> date | None:
    """Naechster Termin strikt nach after_date, inklusive Starttermin."""
    if interval_months < 1:
        raise ValueError("Das Monatsintervall muss mindestens 1 betragen.")

    if end_date is not None and end_date < start_date:
        raise ValueError("Das Enddatum liegt vor dem Startdatum.")

    if after_date is None or after_date < start_date:
        candidate = start_date
    else:
        months_elapsed = (
            (after_date.year - start_date.year) * 12
            + after_date.month - start_date.month
        )
        index = max(0, months_elapsed // interval_months)
        candidate = occurrence_date(start_date, interval_months, index)

        while candidate <= after_date:
            index += 1
            candidate = occurrence_date(start_date, interval_months, index)

    if end_date is not None and candidate > end_date:
        return None

    return candidate


def due_occurrences(
    start_date: date,
    interval_months: int,
    today: date,
    last_occurrence: date | None = None,
    end_date: date | None = None,
    max_count: int = 120,
) -> list[date]:
    """Alle noch nicht verarbeiteten Termine bis einschliesslich heute."""
    if max_count < 1:
        raise ValueError("max_count muss mindestens 1 betragen.")

    result = []
    cursor = last_occurrence

    while len(result) < max_count:
        candidate = next_occurrence(
            start_date,
            interval_months,
            after_date=cursor,
            end_date=end_date,
        )

        if candidate is None or candidate > today:
            break

        result.append(candidate)
        cursor = candidate

    return result
