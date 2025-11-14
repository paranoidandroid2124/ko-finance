"""Common exception types and helpers for ingest pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


class TransientIngestError(RuntimeError):
    """Raised when an ingest step failed due to a recoverable/transient issue."""


class FatalIngestError(RuntimeError):
    """Raised when the ingest step cannot recover without manual intervention."""


@dataclass(frozen=True, slots=True)
class DeadLetterPayload:
    """Structured payload recorded when an ingest task exhausts retries."""

    task_name: str
    retries: int
    context: Mapping[str, Any]
    error: str
    receipt_no: Optional[str] = None
    corp_code: Optional[str] = None
    ticker: Optional[str] = None


__all__ = [
    "TransientIngestError",
    "FatalIngestError",
    "DeadLetterPayload",
]
