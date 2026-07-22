from os import environ
from pathlib import Path

DATABASE_PATH = Path(environ.get("DATABASE_PATH", "data/expenses.db") or ".")
LOG_DIR = Path(environ.get("LOG_DIR", "data/logs"))
