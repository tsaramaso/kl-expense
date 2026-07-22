from sys import stderr
from pathlib import Path

from loguru import logger


def configure_logging(log_dir: Path) -> None:
    logger.remove()  # drop default stderr handler, we set our own

    logger.add(
        stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    )
    logger.add(
        log_dir / "app.log",
        level="INFO",
        rotation="10 MB",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    )
