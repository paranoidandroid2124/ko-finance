"""Shared logging helpers."""

from __future__ import annotations

import logging
import os
from typing import Optional

try:  # pragma: no cover - optional dependency
    from google.cloud import logging as gcp_logging
except Exception:  # pragma: no cover - GCP logging optional
    gcp_logging = None

_CONFIGURED = False
_CLOUD_HANDLER_ATTACHED = False
_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"


def _maybe_setup_google_logging(level: int) -> None:
    """Attach Google Cloud Logging handler when enabled via environment."""
    global _CLOUD_HANDLER_ATTACHED
    if _CLOUD_HANDLER_ATTACHED or gcp_logging is None:
        return
    enabled = os.getenv("ENABLE_GOOGLE_CLOUD_LOGGING", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return
    try:
        client = gcp_logging.Client()
        client.setup_logging(log_level=level)
        _CLOUD_HANDLER_ATTACHED = True
    except Exception as exc:  # pragma: no cover - handler best-effort
        logging.getLogger(__name__).warning("Failed to initialise Google Cloud Logging: %s", exc)


def setup_logging(level: int = logging.INFO, *, fmt: Optional[str] = None) -> None:
    """Ensure root logger is configured once."""
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(level=level, format=fmt or _DEFAULT_FORMAT)
        _CONFIGURED = True
    _maybe_setup_google_logging(level)


def get_logger(name: str, *, level: int = logging.INFO) -> logging.Logger:
    """Return configured logger for a module."""
    setup_logging(level=level)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger
