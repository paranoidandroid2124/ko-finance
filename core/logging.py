"""Shared logging helpers."""

from __future__ import annotations

import logging
from typing import Optional

_CONFIGURED = False
_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"


def setup_logging(level: int = logging.INFO, *, fmt: Optional[str] = None) -> None:
    """Ensure root logger is configured once."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(level=level, format=fmt or _DEFAULT_FORMAT)
    _CONFIGURED = True


def get_logger(name: str, *, level: int = logging.INFO) -> logging.Logger:
    """Return configured logger for a module."""
    setup_logging(level=level)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger

