import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(name: str = "twitter_api") -> logging.Logger:
    """
    Setup application logger with proper formatting and handlers

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Format for logs
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "\033[1;32m%(asctime)s\033[0m [\033[1;36m%(levelname)s\033[0m] %(message)s",
        datefmt=date_format
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler for all logs
    file_handler = logging.FileHandler(
        logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # File handler for errors only
    error_handler = logging.FileHandler(
        logs_dir / f"error_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(log_format, datefmt=date_format)
    error_handler.setFormatter(error_formatter)
    logger.addHandler(error_handler)

    return logger


# Create global logger instance
logger = setup_logger()
