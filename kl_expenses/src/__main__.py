# app/wsgi.py

from src.config import DATABASE_PATH, LOG_DIR
from src.app.context import AppContext
from src.app.create import create_app

if __name__ == "__main__":
    _CTX = AppContext.init_app(DATABASE_PATH, LOG_DIR)
    APP = create_app(_CTX)
