"""CloakBrowser scraper API package.

load_dotenv() runs here so it executes before any submodule import
(even `import app.scraper` triggers this file first).
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

# LOG_LEVEL applies to the app loggers and to uvicorn (access + error logs).
# Unknown values fall back to INFO rather than crashing at import.
_log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    logging.getLogger(_name).setLevel(_log_level)
