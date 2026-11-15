from app.version import APP_VERSION
from app.api.recurring_invoices import router as recurring_invoices_router
from app.api.invoice_pdf import router as invoice_pdf_router
from app.api.invoice_attachments import router as invoice_attachments_router
from app.api.administration import router as administration_router
from app.core.request_security import configure_request_security
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.accounting import router as accounting_router
from app.api.invoices import router as invoices_router
from app.api.xrechnung import router as xrechnung_router
from app.api.partners import router as partners_router
from app.api.accounts import router as accounts_router
from app.api.products import router as products_router
from fastapi import FastAPI

from app.api.auth import router as auth_router


app = FastAPI(
    title="BUHA",
    version=APP_VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

configure_request_security(app)

app.include_router(auth_router)
app.include_router(administration_router)
app.include_router(accounting_router)
app.include_router(invoices_router)
app.include_router(recurring_invoices_router)
app.include_router(xrechnung_router)
app.include_router(invoice_pdf_router)
app.include_router(invoice_attachments_router)
app.include_router(partners_router)
app.include_router(accounts_router)
app.include_router(products_router)


@app.get("/version", include_in_schema=False)
def app_version():
    return {"version": APP_VERSION}


@app.get("/health")
def health():
    return {"status": "ok"}

app.mount("/static", StaticFiles(directory="/app/frontend"), name="static")

@app.get("/", include_in_schema=False)
def frontend_index():
    return FileResponse("/app/frontend/index.html")
