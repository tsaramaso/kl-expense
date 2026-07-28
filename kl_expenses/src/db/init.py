# app/init.py
from pathlib import Path
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlite3 import Connection as SQLite3Connection
from sqlalchemy.pool import ConnectionPoolEntry


def make_session(engine: Engine) -> sessionmaker[Session]:
    """Build once at startup; call the result to get a new Session each time."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def _set_sqlite_pragmas(
    dbapi_connection: SQLite3Connection, connection_record: ConnectionPoolEntry
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def init_db_engine(db_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}")
    event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine
