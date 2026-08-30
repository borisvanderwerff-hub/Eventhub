from __future__ import annotations

import logging
import logging.handlers

from .paths import logs_directory

_CONFIGURED = False


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root 'eventhub_server' logger once; safe to call repeatedly."""
    global _CONFIGURED
    logger = logging.getLogger("eventhub_server")
    if _CONFIGURED:
        return logger
    logger.setLevel(level)

    log_file = logs_directory() / "eventhub-server.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _CONFIGURED = True
    logger.info("Logging gestart. Logbestand: %s", log_file)
    return logger


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"eventhub_server.{name}")
