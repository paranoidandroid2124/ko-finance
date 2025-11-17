"""Utilities for persisting and maintaining ingest dead-letter entries."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy.orm import Session

from models.ingest_dead_letter import IngestDeadLetter
from services.ingest_metrics import set_dlq_size

logger = logging.getLogger(__name__)
_MAX_ERROR_LENGTH = 4000
_KNOWN_STATUSES: Sequence[str] = ("pending", "requeued", "completed")


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


def _refresh_gauge(db: Session) -> None:
    try:
        for status in _KNOWN_STATUSES:
            count = db.query(IngestDeadLetter).filter(IngestDeadLetter.status == status).count()
            set_dlq_size(status, count)
    except Exception as exc:  # pragma: no cover - metrics best effort
        logger.debug("Failed to refresh DLQ gauge: %s", exc)


def refresh_metrics(db: Session) -> None:
    """Force-refresh the Prometheus gauge for DLQ status counts."""
    _refresh_gauge(db)


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
    _refresh_gauge(db)
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
    _refresh_gauge(db)


def mark_completed(db: Session, letter: IngestDeadLetter) -> None:
    letter.status = "completed"
    letter.next_run_at = None
    db.add(letter)
    db.commit()
    _refresh_gauge(db)


def list_dead_letters(
    db: Session,
    *,
    status: Optional[str] = None,
    task_name: Optional[str] = None,
    limit: int = 50,
) -> Sequence[IngestDeadLetter]:
    """Return DLQ entries filtered by status/task name."""
    query = db.query(IngestDeadLetter)
    if status and status.lower() != "all":
        query = query.filter(IngestDeadLetter.status == status.lower())
    if task_name:
        query = query.filter(IngestDeadLetter.task_name == task_name)
    limit = max(1, min(int(limit), 500))
    return query.order_by(IngestDeadLetter.created_at.desc()).limit(limit).all()


def get_dead_letter(db: Session, letter_id: str | uuid.UUID) -> Optional[IngestDeadLetter]:
    """Fetch a dead-letter entry by UUID string."""
    try:
        identifier = letter_id if isinstance(letter_id, uuid.UUID) else uuid.UUID(str(letter_id))
    except (ValueError, TypeError):
        return None
    return db.get(IngestDeadLetter, identifier)


__all__ = [
    "get_dead_letter",
    "list_dead_letters",
    "mark_completed",
    "mark_requeued",
    "record_dead_letter",
    "refresh_metrics",
]
