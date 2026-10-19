"""API and conversion tests — no browser required (scraper.scrape is monkeypatched)."""
import pytest
from fastapi.testclient import TestClient

import app.scraper as scraper
from app.main import app


@pytest.fixture(autouse=True)
def _no_auth_by_default(monkeypatch):
    # A local .env may set AUTH_TOKEN (loaded via dotenv); tests opt in explicitly.
    monkeypatch.delenv("AUTH_TOKEN", raising=False)


client = TestClient(app)


def test_health_needs_no_auth(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "secret")
    assert client.get("/health").status_code == 200


def test_root_links_to_docs():
    r = client.get("/")
    assert r.status_code == 200
    assert "/docs" in r.text


def test_scrape_rejects_unknown_format():
    r = client.get("/scrape", params={"url": "https://example.com", "format": "pdf"})
    assert r.status_code == 422


def test_scrape_rejects_non_http_scheme():
    r = client.get("/scrape", params={"url": "file:///etc/passwd"})
    assert r.status_code == 422


def test_auth_enforced_when_token_set(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "secret")
    params = {"url": "https://example.com"}
    assert client.get("/scrape", params=params).status_code == 401
    assert (
        client.get("/scrape", params=params, headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: _ok("hi"))
    r = client.get("/scrape", params=params, headers={"Authorization": "Bearer secret"})
    assert r.status_code == 200
    assert r.text == "hi"


def test_scrape_failure_maps_to_502(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("net::ERR_NAME_NOT_RESOLVED")

    monkeypatch.setattr(scraper, "scrape", boom)
    r = client.get("/scrape", params={"url": "https://nope.invalid"})
    assert r.status_code == 502
    assert "ERR_NAME_NOT_RESOLVED" in r.json()["detail"]


def test_screenshot_returns_png(monkeypatch):
    png = b"\x89PNG\r\n\x1a\nfake"
    monkeypatch.setattr(scraper, "scrape", lambda *a, **k: _ok(png))
    r = client.get("/scrape", params={"url": "https://example.com", "format": "screenshot"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == png


def test_html_to_markdown_conversion():
    md = scraper._markdown.convert("<h1>Hi there</h1><p>Some <b>bold</b> text.</p>")
    assert "# Hi there" in md
    assert "**bold**" in md


async def _ok(value):
    return value
