"""Single-page scraping via CloakBrowser (stealth Playwright wrapper)."""
import asyncio
import io
import json
import logging
import os
import re

from cloakbrowser import launch_context_async
from fast_html2md import HTMLToMarkdown

logger = logging.getLogger("scraper.core")

_markdown = HTMLToMarkdown()
_semaphore = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_SCRAPES", "3")))

# Chromium inside a container: no sandbox (runs as root), and /dev/shm is tiny by default.
_CONTAINER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _launch_kwargs() -> dict:
    kwargs: dict = {"args": list(_CONTAINER_ARGS)}
    if proxy := os.getenv("PROXY_URL"):
        kwargs["proxy"] = proxy
    if not _env_bool("CB_HEADLESS", True):
        kwargs["headless"] = False
    if _env_bool("CB_HUMANIZE"):
        kwargs["humanize"] = True
        if preset := os.getenv("CB_HUMAN_PRESET"):
            kwargs["human_preset"] = preset
    if _env_bool("CB_GEOIP"):
        kwargs["geoip"] = True
    if tz := os.getenv("CB_TIMEZONE"):
        kwargs["timezone"] = tz
    if locale := os.getenv("CB_LOCALE"):
        kwargs["locale"] = locale
    if ua := os.getenv("CB_USER_AGENT"):
        kwargs["user_agent"] = ua
    if extra := os.getenv("CB_ARGS"):
        kwargs["args"] += [a.strip() for a in extra.split(",") if a.strip()]
    if raw := os.getenv("CB_LAUNCH_KWARGS"):
        # Escape hatch for any launch_context option not covered above.
        overrides = json.loads(raw)
        kwargs.update(overrides)
        kwargs["args"] = list(_CONTAINER_ARGS) + list(overrides.get("args", []))
    return kwargs


def _ocr(png: bytes) -> str:
    import pytesseract
    from PIL import Image

    return pytesseract.image_to_string(Image.open(io.BytesIO(png)))


def _redact(url: str) -> str:
    """Hide proxy credentials in logs: scheme://user:pass@host -> scheme://***@host."""
    return re.sub(r"://[^/@]+@", "://***@", url)


async def scrape(url: str, fmt: str, full_page: bool = True):
    """Scrape one page. Returns html/markdown as str, screenshot PNG as bytes."""
    kwargs = _launch_kwargs()
    if logger.isEnabledFor(logging.DEBUG):
        safe_kwargs = dict(kwargs)
        if "proxy" in safe_kwargs:
            safe_kwargs["proxy"] = _redact(str(safe_kwargs["proxy"]))
        logger.debug("launch kwargs: %s", safe_kwargs)
    async with _semaphore:
        ctx = await launch_context_async(**kwargs)
        try:
            page = await ctx.new_page()
            await page.goto(url, wait_until="load")
            await page.wait_for_timeout(500)  # let late JS settle
            if fmt in ("html", "markdown"):
                html = await page.content()
                return html if fmt == "html" else _markdown.convert(html)
            png = await page.screenshot(full_page=full_page)
            return png if fmt == "screenshot" else _ocr(png)
        finally:
            await ctx.close()
