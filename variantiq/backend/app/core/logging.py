"""Logging configuration using loguru."""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    """
    Configure application logging with loguru.

    Sets up console and file logging with rotation and retention.
    """
    # Remove default handler
    logger.remove()

    # Console logging
    logger.add(
        sys.stdout,
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=settings.DEBUG,
    )

    # File logging (if configured)
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(log_path),
            format=settings.LOG_FORMAT,
            level=settings.LOG_LEVEL,
            rotation=settings.LOG_ROTATION,
            retention=settings.LOG_RETENTION,
            compression="zip",
            backtrace=True,
            diagnose=settings.DEBUG,
        )

    logger.info(f"Logging configured for {settings.ENVIRONMENT} environment")
    logger.info(f"Log level: {settings.LOG_LEVEL}")


def get_logger(name: str):
    """
    Get a logger instance for a specific module.

    Args:
        name: Module name

    Returns:
        Logger instance
    """
    return logger.bind(name=name)
