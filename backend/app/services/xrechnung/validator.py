"""KoSIT-XRechnung-Validierung über internen HTTP-Dienst."""

import os
from xml.etree import ElementTree as ET

import httpx


class XRechnungValidationError(ValueError):
    """XRechnung konnte nicht erfolgreich validiert werden."""


REPORT_NS = "http://www.xoev.de/de/validator/varl/1"

VALIDATOR_URL = os.getenv(
    "BUHA_XRECHNUNG_VALIDATOR_URL",
    "http://xrechnung-validator:8080/validate",
)


def parse_validation_report(report_xml: bytes) -> dict:
    """KoSIT-Prüfbericht auswerten."""
    try:
        root = ET.fromstring(report_xml)
    except ET.ParseError as error:
        raise XRechnungValidationError(
            "KoSIT hat keinen gültigen XML-Prüfbericht geliefert."
        ) from error

    if root.tag != f"{{{REPORT_NS}}}report":
        raise XRechnungValidationError(
            "KoSIT-Antwort enthält keinen gültigen Prüfbericht."
        )

    ns = {"rep": REPORT_NS}
    assessment = root.find("rep:assessment", ns)

    if assessment is None:
        raise XRechnungValidationError(
            "KoSIT-Prüfbericht enthält keine Bewertung."
        )

    accepted = (
        root.attrib.get("valid") == "true"
        and assessment.find("rep:accept", ns) is not None
        and assessment.find("rep:reject", ns) is None
    )

    messages = []
    for message in root.findall(".//rep:message", ns):
        level = message.attrib.get("level", "")
        if level not in {"error", "warning", "fatal"}:
            continue

        messages.append({
            "level": level,
            "code": message.attrib.get("code", ""),
            "message": " ".join("".join(message.itertext()).split()),
        })

    return {
        "accepted": accepted,
        "messages": messages,
    }


def validate_xrechnung(xml_bytes: bytes) -> dict:
    """XML an KoSIT senden; bei REJECT oder Ausfall abbrechen."""
    if not xml_bytes:
        raise XRechnungValidationError(
            "Keine XML-Daten zur Validierung vorhanden."
        )

    try:
        response = httpx.post(
            VALIDATOR_URL,
            content=xml_bytes,
            headers={"Content-Type": "application/xml"},
            timeout=30.0,
        )
        if response.status_code not in (200, 406):
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise XRechnungValidationError(
            "KoSIT-Validator ist nicht erreichbar oder meldet einen technischen Fehler."
        ) from error

    result = parse_validation_report(response.content)

    if not result["accepted"]:
        details = "; ".join(
            f'{item["code"]}: {item["message"]}'
            for item in result["messages"][:5]
        )
        raise XRechnungValidationError(
            "XRechnung nicht konform: "
            + (details or "KoSIT hat die Rechnung zurückgewiesen.")
        )

    return result
