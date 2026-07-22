# app/init.py
from pathlib import Path
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.app.models import Base


def make_session(engine: Engine) -> sessionmaker[Session]:
    """Build once at startup; call the result to get a new Session each time."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db_engine(db_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine
