# cloakbrowser-fast-api

Single-page web scraper REST API built on [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) (stealth Chromium), with [fast-html2md](https://github.com/ancs21/fast-html2md) and [pytesseract](https://github.com/madmaze/pytesseract).

`GET /scrape?url=...&format=html|markdown|screenshot|ocr` → raw HTML, Markdown, a full-page PNG, or OCR text.

## Quickstart (local)

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Open http://localhost:8000/docs — Swagger UI with an **Authorize** button and a live `/scrape` form.

## Quickstart (Docker)

```bash
docker compose up --build
# or: docker build -t scraper . && docker run -p 8000:8000 -e AUTH_TOKEN=changeme scraper
```

The image ships with tesseract (OCR) and the CloakBrowser Chromium binary pre-downloaded.

## API

| Endpoint | Auth | Description |
|---|---|---|
| `GET /scrape` | bearer (if `AUTH_TOKEN` set) | Scrape one page |
| `GET /health` | none | Liveness check |
| `GET /docs`, `/redoc`, `/openapi.json` | none | OpenAPI UIs/schema |

### `/scrape` parameters

| Param | Default | Description |
|---|---|---|
| `url` | — | Page to scrape (`http`/`https` only) |
| `format` | `html` | `html`, `markdown`, `screenshot`, `ocr` |
| `full_page` | `true` | Screenshot/OCR: whole page instead of just the viewport |

Responses are raw content: `text/html`, `text/markdown`, `image/png`, `text/plain`. Fetch failures return `502`; auth failures `401`; bad params `422`.

```bash
curl 'http://localhost:8000/scrape?url=https://example.com&format=markdown' \
  -H 'Authorization: Bearer changeme'
```

## Configuration

All settings load from a **`.env`** file (via python-dotenv) as well as from the process environment — process env always wins. Start from the template:

```bash
cp .env.example .env   # docker compose also reads .env automatically for port/secret interpolation
```

| Env var | Default | Description |
|---|---|---|
| `PORT` | `8000` | HTTP port (local `uvicorn --port` and Docker alike) |
| `AUTH_TOKEN` | — | If set, `/scrape` requires `Authorization: Bearer <token>`. Unset = open API (dev only) |
| `PROXY_URL` | — | Server-wide proxy, `http://` or `socks5://` |
| `CLOAKBROWSER_LICENSE_KEY` | — | Free key via `cloakbrowser login`, or paid. Unset falls back to the older free build |
| `MAX_CONCURRENT_SCRAPES` | `3` | Concurrent browser sessions (each uses ~300-500MB) |
| `LOG_LEVEL` | `INFO` | `DEBUG`\|`INFO`\|`WARNING`\|`ERROR` — app logs **and** uvicorn access logs. `DEBUG` adds launch kwargs (proxy credentials redacted) |

Every finished request logs one line — `scraped url=... format=markdown bytes=1234 in 3.21s` (INFO) or the failure traceback (ERROR). For debugging: `LOG_LEVEL=DEBUG docker compose up`.

### CloakBrowser options

| Env var | Maps to | Default |
|---|---|---|
| `CB_HEADLESS` | `headless` | `true` |
| `CB_HUMANIZE` | `humanize` (human-like mouse/typing/scroll) | `false` |
| `CB_HUMAN_PRESET` | `human_preset` (`default`/`careful`) | — |
| `CB_GEOIP` | `geoip` (timezone/locale from proxy IP) | `false` |
| `CB_TIMEZONE` | `timezone` | — |
| `CB_LOCALE` | `locale` | — |
| `CB_USER_AGENT` | `user_agent` | — |
| `CB_ARGS` | `args` (comma-separated extra Chromium flags) | — |
| `CB_LAUNCH_KWARGS` | raw JSON merged into `launch_context_async(...)` — anything else (viewport, storage_state, ...) | — |

Booleans accept `1/true/yes/on`.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

Tests cover the API surface (auth, validation, format handling) and HTML→Markdown conversion; they never launch a browser.

## Notes

- OCR is a fallback for pages that render content into canvas/images; it takes seconds per page.
- Each scrape launches a fresh browser session (stateless, no shared profile). Proxy credentials never come from callers — only from the server's `PROXY_URL`.
