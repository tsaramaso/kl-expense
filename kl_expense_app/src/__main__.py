# app/__main__.py

from pathlib import Path

from src.cli import build_parser, dispatch
from src.config import DATABASE_PATH, LOG_DIR
from src.context import AppContext


def main(db_path: Path, log_dir: Path) -> None:
    args = build_parser().parse_args()
    ctx = AppContext.init_app(db_path, log_dir)
    dispatch(args, ctx.session_factory)


if __name__ == "__main__":
    main(DATABASE_PATH, LOG_DIR)
