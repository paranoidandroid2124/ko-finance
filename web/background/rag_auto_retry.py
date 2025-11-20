"""Placeholder for deprecated admin RAG auto-retry scheduler."""

from __future__ import annotations

from core.logging import get_logger

logger = get_logger(__name__)


def start_retry_scheduler() -> None:
    """Admin RAG auto-retry is disabled."""
    logger.info("Admin RAG auto-retry scheduler is disabled.")


__all__ = ["start_retry_scheduler"]
