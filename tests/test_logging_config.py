import logging

from app.logging_config import configure_logging


def test_logging_writes_to_daily_application_log_without_duplicate_handlers(tmp_path):
    logger = configure_logging(log_directory=tmp_path, level="INFO")
    logger = configure_logging(log_directory=tmp_path, level="INFO")
    file_handlers = [
        handler for handler in logger.handlers
        if getattr(handler, "_paper_trading_file", False)
    ]

    try:
        assert len(file_handlers) == 1
        assert not logger.isEnabledFor(logging.DEBUG)
        logger.info("candidate training log test")
        file_handlers[0].flush()
        assert "candidate training log test" in (tmp_path / "paper-trading.log").read_text()
    finally:
        for handler in list(logger.handlers):
            if getattr(handler, "_paper_trading_console", False) or getattr(handler, "_paper_trading_file", False):
                logger.removeHandler(handler)
                handler.close()
