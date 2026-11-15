from app.api.dependencies import CurrentUser, DatabaseSession
"""XRechnung API – XML import preview."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.dependencies import CurrentUser
from app.services.xrechnung.ubl import (
    UBLParseError,
    parse_ubl_invoice,
)
from app.services.xrechnung.validator import (
    XRechnungValidationError,
    validate_xrechnung,
)

router = APIRouter(
    prefix="/api/xrechnung",
    tags=["XRechnung"],
)

MAX_XML_BYTES = 10 * 1024 * 1024



def parse_invoice_xml(content):
    """UBL oder CII anhand des XML-Wurzelelements erkennen."""
    from defusedxml import ElementTree as SafeET
    from app.services.xrechnung.cii import (
        CIIParseError,
        parse_cii_invoice,
    )

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "XML-Datei überschreitet 10 MB.")

    try:
        root = SafeET.fromstring(content)
    except Exception as exc:
        raise HTTPException(
            422, "XML-Datei ist syntaktisch ungültig."
        ) from exc

    if root.tag == (
        "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"
    ):
        return parse_ubl_invoice(content)

    if root.tag == (
        "{urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100}"
        "CrossIndustryInvoice"
    ):
        try:
            return parse_cii_invoice(content)
        except CIIParseError as exc:
            raise HTTPException(422, str(exc)) from exc

    raise HTTPException(
        422,
        "Unbekanntes Rechnungsformat. Unterstützt werden UBL und CII.",
    )


@router.post("/incoming/preview")
async def preview_incoming_xrechnung(
    user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
):
    filename = file.filename or ""

    if not filename.lower().endswith(".xml"):
        raise HTTPException(
            422,
            "Bitte eine XML-Datei hochladen.",
        )

    content = await file.read(MAX_XML_BYTES + 1)

    if len(content) > MAX_XML_BYTES:
        raise HTTPException(
            413,
            "XML-Datei überschreitet 10 MB.",
        )

    try:
        result = parse_invoice_xml(content)
    except UBLParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        validation = validate_xrechnung(content)
    except XRechnungValidationError as exc:
        raise HTTPException(
            422,
            "XRechnung-Validierung fehlgeschlagen: " + str(exc),
        ) from exc

    result["validated"] = True
    result["validation"] = validation

    from app.services.xrechnung.import_checks import (
        match_supplier,
        check_duplicate,
    )

    supplier_match = match_supplier(
        db,
        result.get("supplier") or {},
    )

    result["supplier_match"] = supplier_match

    result["duplicate_check"] = check_duplicate(
        db,
        supplier_match.get("partner_id"),
        result.get("invoice_number"),
    )

    from app.services.xrechnung.import_prepare import (
        XRechnungImportError,
        prepare_import,
    )

    try:
        prepare_import(result)
        result["importable"] = True
        result["import_error"] = None
    except XRechnungImportError as exc:
        result["importable"] = False
        result["import_error"] = str(exc)

    return result


@router.post("/incoming/import", status_code=201)
async def import_incoming_xrechnung(
    user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(...),
    partner_id: int = Form(...),
    account_id: int = Form(...),
):
    """Importiert ausschließlich nach ausdrücklicher Bestätigung."""

    from app.services.xrechnung.import_prepare import (
        XRechnungImportError,
        prepare_import,
    )
    from app.services.xrechnung.import_save import (
        save_incoming_xrechnung,
    )

    filename = file.filename or ""

    if not filename.lower().endswith(".xml"):
        raise HTTPException(
            422, "Bitte eine XML-Datei auswählen."
        )

    content = await file.read(MAX_XML_BYTES + 1)

    if len(content) > MAX_XML_BYTES:
        raise HTTPException(
            413, "XML-Datei überschreitet 10 MB."
        )

    if not content:
        raise HTTPException(
            422, "Die XML-Datei ist leer."
        )

    try:
        parsed = parse_invoice_xml(content)
    except UBLParseError as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        validate_xrechnung(content)
    except XRechnungValidationError as exc:
        raise HTTPException(
            422,
            "XRechnung-Validierung fehlgeschlagen: " + str(exc),
        ) from exc

    try:
        prepare_import(parsed)

        result = save_incoming_xrechnung(
            db,
            parsed=parsed,
            xml_content=content,
            original_filename=filename,
            partner_id=partner_id,
            account_id=account_id,
        )

    except XRechnungImportError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc

    return result
