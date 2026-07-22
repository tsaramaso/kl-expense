# app/wsgi.py

from src.config import DATABASE_PATH, LOG_DIR
from src.context import AppContext
from src.flask_app import create_app

_CTX = AppContext.init_app(DATABASE_PATH, LOG_DIR)

APP = create_app(_CTX)
