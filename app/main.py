"""FastAPI front door for the CloakBrowser single-page scraper."""
import logging
import os
import time
from typing import Literal
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import scraper

logger = logging.getLogger("scraper.api")

FORMAT_MEDIA_TYPES = {
    "html": "text/html",
    "markdown": "text/markdown",
    "screenshot": "image/png",
    "ocr": "text/plain",
}

app = FastAPI(
    title="CloakBrowser Scraper",
    version="1.0.0",
    description=(
        "Single-page scraper backed by CloakBrowser (stealth Chromium).\n\n"
        "Set `AUTH_TOKEN` on the server, then click **Authorize** below and paste the token. "
        "With `AUTH_TOKEN` unset the API is open (local dev only)."
    ),
    openapi_tags=[{"name": "scrape", "description": "Scrape a single page as html, markdown, screenshot or OCR text."}],
)

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    token = os.getenv("AUTH_TOKEN", "")
    if token and (credentials is None or credentials.credentials != token):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def index() -> HTMLResponse:
    return HTMLResponse(
        "<h1>CloakBrowser Scraper</h1>"
        "<p><a href='/docs'>Swagger UI</a> &middot; <a href='/redoc'>ReDoc</a> "
        "&middot; <a href='/health'>Health</a></p>"
    )


@app.get(
    "/scrape",
    tags=["scrape"],
    responses={
        200: {
            "description": "Scraped page content in the requested format.",
            "content": {
                "text/html": {},
                "text/markdown": {},
                "image/png": {},
                "text/plain": {},
            },
        },
        401: {"description": "Missing or invalid bearer token"},
        422: {"description": "Invalid query parameters"},
        502: {"description": "Target page could not be fetched"},
    },
)
async def scrape(
    url: str = Query(..., description="Page to scrape (http/https).", examples=["https://example.com"]),
    format: Literal["html", "markdown", "screenshot", "ocr"] = Query(
        "html",
        description=(
            "Output format: raw `html`; `markdown` (fast-html2md); "
            "`screenshot` (full-page PNG); `ocr` (tesseract text from the screenshot)."
        ),
    ),
    full_page: bool = Query(
        True, description="For screenshot/ocr: capture the whole page, not just the viewport."
    ),
    _auth: None = Depends(require_auth),
) -> Response:
    if urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="url must be http(s)")
    start = time.perf_counter()
    try:
        result = await scraper.scrape(url, format, full_page)
    except Exception as exc:  # navigation/timeout/DNS failures all surface as 502
        logger.exception(
            "scrape failed url=%s format=%s after %.2fs", url, format, time.perf_counter() - start
        )
        raise HTTPException(status_code=502, detail=f"scrape failed: {exc}") from exc
    logger.info(
        "scraped url=%s format=%s bytes=%d in %.2fs",
        url,
        format,
        len(result),
        time.perf_counter() - start,
    )
    return Response(content=result, media_type=FORMAT_MEDIA_TYPES[format])
