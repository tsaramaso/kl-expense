# app/init.py
from pathlib import Path
from sqlalchemy import Engine, create_engine

from src.app.models import Base


def init_db_engine(db_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine
