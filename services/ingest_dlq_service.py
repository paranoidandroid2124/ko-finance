"""Utilities for persisting and maintaining ingest dead-letter entries."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from sqlalchemy.orm import Session

from models.ingest_dead_letter import IngestDeadLetter

logger = logging.getLogger(__name__)
_MAX_ERROR_LENGTH = 4000


def _normalize_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    def coerce(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Mapping):
            return {str(key): coerce(val) for key, val in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [coerce(item) for item in value]
        return str(value)

    return {str(key): coerce(val) for key, val in payload.items()}


def record_dead_letter(
    db: Session,
    *,
    task_name: str,
    payload: Mapping[str, Any],
    error: str,
    retries: int,
    receipt_no: Optional[str] = None,
    corp_code: Optional[str] = None,
    ticker: Optional[str] = None,
) -> IngestDeadLetter:
    """Persist a dead-letter entry and return it."""
    safe_error = (error or "")[: _MAX_ERROR_LENGTH]
    normalized_payload = dict(_normalize_payload(payload))
    # Ensure payload is JSON serializable (defensive).
    try:
        json.dumps(normalized_payload)
    except TypeError:
        normalized_payload = {"__raw__": str(payload)}

    letter = IngestDeadLetter(
        task_name=task_name,
        receipt_no=receipt_no,
        corp_code=corp_code,
        ticker=ticker,
        payload=normalized_payload,
        error=safe_error,
        retries=max(0, int(retries)),
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    logger.warning(
        "Recorded ingest DLQ entry (task=%s receipt=%s retries=%s).",
        task_name,
        receipt_no,
        retries,
    )
    return letter


def mark_requeued(
    db: Session,
    letter: IngestDeadLetter,
    *,
    next_run_at: Optional[datetime] = None,
) -> None:
    letter.status = "requeued"
    letter.next_run_at = next_run_at
    db.add(letter)
    db.commit()


def mark_completed(db: Session, letter: IngestDeadLetter) -> None:
    letter.status = "completed"
    letter.next_run_at = None
    db.add(letter)
    db.commit()


__all__ = ["record_dead_letter", "mark_requeued", "mark_completed"]

