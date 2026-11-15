from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

MAX_CONTENT_LENGTH = 2 * 1024 * 1024
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def configure_request_security(app):
    @app.middleware("http")
    async def request_security(request: Request, call_next):
        if request.method not in SAFE_METHODS:
            content_length = request.headers.get("content-length")

            if content_length is not None:
                try:
                    size = int(content_length)
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Ungueltige Anfragegroesse."},
                    )

                if size < 0 or size > MAX_CONTENT_LENGTH:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Anfrage zu gross."},
                    )

            origin = request.headers.get("origin")

            if origin:
                configured = get_settings().app_url.rstrip("/")

                try:
                    parsed_origin = urlsplit(origin)
                    parsed_expected = urlsplit(configured)

                    allowed = (
                        parsed_origin.scheme == parsed_expected.scheme
                        and parsed_origin.netloc == parsed_expected.netloc
                    )
                except ValueError:
                    allowed = False

                if not allowed:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Ungueltiger Anfrageursprung."},
                    )

        return await call_next(request)
