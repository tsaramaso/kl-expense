# app/db_session.py
from flask import current_app, g
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import Engine

from src.app.context import AppContext

def make_session(engine: Engine) -> sessionmaker[Session]:
    """Build once at startup; call the result to get a new Session each time."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def open_session() -> None:
    ctx: AppContext = current_app.extensions["ctx"]
    g.db = ctx.session_factory()


def close_session(exception: BaseException | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def get_session() -> Session:
    return g.db
