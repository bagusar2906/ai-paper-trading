"""Application logging for the paper-trading API and worker processes."""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
APP_LOGGER_NAME = "app"


def configure_logging(
    *,
    log_directory: Path | str = "data/logs",
    level: str | None = None,
) -> logging.Logger:
    """Configure console and daily rotating file logs without duplicate handlers."""
    logger = logging.getLogger(APP_LOGGER_NAME)
    configured_level = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    logger.setLevel(getattr(logging, configured_level, logging.INFO))
    logger.propagate = False

    # Market-data libraries can be very chatty during routine polling. Their
    # warnings/errors remain visible, while request-by-request detail is only
    # available when explicitly troubleshooting with LOG_LEVEL=DEBUG.
    for library_logger in ("yfinance", "urllib3", "peewee"):
        logging.getLogger(library_logger).setLevel(
            logging.DEBUG if configured_level == "DEBUG" else logging.WARNING
        )

    directory = Path(log_directory)
    directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT)

    if not any(getattr(handler, "_paper_trading_console", False) for handler in logger.handlers):
        console = logging.StreamHandler()
        console._paper_trading_console = True
        console.setFormatter(formatter)
        logger.addHandler(console)

    if not any(getattr(handler, "_paper_trading_file", False) for handler in logger.handlers):
        file_handler = TimedRotatingFileHandler(
            directory / "paper-trading.log",
            when="midnight",
            backupCount=14,
            encoding="utf-8",
        )
        file_handler._paper_trading_file = True
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
