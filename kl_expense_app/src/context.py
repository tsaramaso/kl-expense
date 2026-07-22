from dataclasses import dataclass
from pathlib import Path
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.logger import configure_logging
from src.db import init_db_engine, make_session_factory


@dataclass(frozen=True)
class AppContext:
    engine: Engine
    session_factory: sessionmaker[Session]

    @staticmethod
    def init_app(db_path: Path, log_path: Path) -> "AppContext":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.mkdir(parents=True, exist_ok=True)
        configure_logging(log_path)
        engine = init_db_engine(db_path)
        session_factory = make_session_factory(engine)
        return AppContext(engine=engine, session_factory=session_factory)
