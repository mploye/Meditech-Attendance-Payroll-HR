import sys
from pathlib import Path

from loguru import logger

_LOG_FILE = Path(__file__).resolve().parent / "logs" / "connector.log"


def get_logger():
    """Configured loguru logger writing to stdout and a rotating file."""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        logger.add(str(_LOG_FILE), level="DEBUG", rotation="10 MB", retention="7 days")
    except OSError:
        pass
    return logger