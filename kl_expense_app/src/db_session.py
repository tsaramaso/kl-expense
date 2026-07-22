# app/db_session.py
from flask import current_app, g
from sqlalchemy.orm import Session

from src.context import AppContext


def open_session() -> None:
    ctx: AppContext = current_app.extensions["ctx"]
    g.db = ctx.session_factory()


def close_session(exception: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_session() -> Session:
    return g.db
