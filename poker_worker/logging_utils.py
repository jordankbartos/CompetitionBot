import logging
import os

from pythonjsonlogger import jsonlogger

_configured = False


def configure_logging():
    """
    Consolidated logging configuration for the project.
    Sets the log level and format including file name and line number.
    """
    global _configured
    if _configured:
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    # Using a custom JSON formatter to ensure multi-line tracebacks are logged as single entries
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(filename)s %(lineno)d %(message)s"
    )

    # Configure the root logger to use the JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Prevent duplicate logs from default handler if force=True isn't enough
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.addHandler(handler)

    _configured = True


def get_logger(name: str):
    """
    Returns a configured logger instance.
    """
    configure_logging()
    return logging.getLogger(name)
