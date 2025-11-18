"""Celery helpers for filing ingestion workflows."""

from __future__ import annotations

from typing import Optional

from core.logging import get_logger

try:  # pragma: no cover - optional task import
    from parse.tasks import process_filing
except Exception:  # pragma: no cover
    process_filing = None  # type: ignore[assignment]

logger = get_logger(__name__)


def enqueue_process_filing(filing_id: str) -> None:
    """Queue the Celery task that processes a filing."""

    if not process_filing:
        raise RuntimeError("process_filing task is unavailable; Celery worker not configured.")

    try:
        process_filing.delay(filing_id)
    except Exception as exc:  # pragma: no cover - Celery failure
        logger.warning("Failed to enqueue filing process task (id=%s): %s", filing_id, exc, exc_info=True)
        raise


__all__ = ["enqueue_process_filing"]
