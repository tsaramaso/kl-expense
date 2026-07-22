# app/wsgi.py

from app.config import DATABASE_PATH, LOG_DIR
from app.context import AppContext
from app.flask_app import create_app

_CTX = AppContext.init_app(DATABASE_PATH, LOG_DIR)

APP = create_app(_CTX)
