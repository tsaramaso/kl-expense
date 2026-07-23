# kl_expenses/src/app/config.py
from os import environ
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_FOLDER = PROJECT_ROOT / "templates"
STATIC_FOLDER = PROJECT_ROOT / "static"

DATABASE_PATH = Path(environ.get("DATABASE_PATH", "data/operations.db") or ".")
LOG_DIR = Path(environ.get("LOG_DIR", "data/logs"))

SECRET_KEY = environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. "
        'Generate one with: python3 -c "import secrets; print(secrets.token_hex(32))"'
    )

FORCE_SECURE_COOKIE = environ.get("FORCE_SECURE_COOKIE") == "1"
