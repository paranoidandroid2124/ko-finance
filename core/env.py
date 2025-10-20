"""Environment variable helpers."""

from __future__ import annotations

import logging
import os
from typing import Optional, TypeVar

from core.logging import get_logger

T = TypeVar("T", int, float)

logger = get_logger(__name__)


def env_str(key: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(key, default)
    if value is None:
        logger.debug("Environment variable %s not set. Using default=%s.", key, default)
    return value


def env_int(key: str, default: int, *, minimum: Optional[int] = None) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
        if minimum is not None and value < minimum:
            raise ValueError
        return value
    except ValueError:
        logger.warning("Invalid %s value '%s'. Falling back to %d.", key, raw, default)
        return default


def env_float(key: str, default: float, *, minimum: Optional[float] = None) -> float:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = float(raw)
        if minimum is not None and value < minimum:
            raise ValueError
        return value
    except ValueError:
        logger.warning("Invalid %s value '%s'. Falling back to %.2f.", key, raw, default)
        return default


def env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    logger.warning("Invalid boolean env %s='%s'. Using default=%s.", key, raw, default)
    return default

