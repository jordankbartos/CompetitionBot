import logging
import os

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
    log_format = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"

    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        force=True,  # Ensure this config overrides any previous one
    )
    _configured = True


def get_logger(name: str):
    """
    Returns a configured logger instance.
    """
    configure_logging()
    return logging.getLogger(name)
