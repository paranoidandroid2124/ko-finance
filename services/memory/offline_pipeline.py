"""Utilities that promote short-term summaries into long-term memory."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Sequence

from core.logging import get_logger
from services.embedding_utils import embed_text
from services.memory.long_term_store import persist_records
from services.memory.models import MemoryRecord, SessionSummaryEntry
from services.memory.session_store import build_default_store

logger = get_logger(__name__)
UTC = timezone.utc


def _extract_score(entry: SessionSummaryEntry) -> float:
    raw = entry.metadata.get("importance_score") if isinstance(entry.metadata, dict) else None
    if raw is None:
        return 0.5
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.5


def _build_summary_text(entry: SessionSummaryEntry) -> str:
    if entry.highlights:
        return "; ".join(entry.highlights)
    if isinstance(entry.metadata, dict):
        summary = entry.metadata.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return entry.topic


def _entry_to_record(entry: SessionSummaryEntry) -> MemoryRecord | None:
    metadata = dict(entry.metadata or {})
    tenant_id = metadata.get("tenant_id")
    user_id = metadata.get("user_id")
    if not tenant_id or not user_id:
        return None

    summary_text = _build_summary_text(entry)
    if not summary_text.strip():
        return None

    embedding = embed_text(summary_text)
    return MemoryRecord(
        tenant_id=str(tenant_id),
        user_id=str(user_id),
        topic=entry.topic,
        summary=summary_text,
        embedding=embedding,
        importance_score=_extract_score(entry),
    )


def run_long_term_update() -> int:
    """Promote expired session summaries into the long-term store.

    Returns
    -------
    int
        Number of memory records persisted.
    """

    store = build_default_store()
    now = datetime.now(UTC)
    session_ids = list(store.iter_session_ids())
    promoted: List[MemoryRecord] = []

    for session_id in session_ids:
        entries = store.load(session_id)
        remaining: List[SessionSummaryEntry] = []
        for entry in entries:
            if not entry.is_expired(at=now):
                remaining.append(entry)
                continue
            record = _entry_to_record(entry)
            if record:
                promoted.append(record)
        store.delete(session_id)
        for entry in remaining:
            store.save(entry)

    if not promoted:
        logger.info("No expired session summaries found for long-term promotion.")
        return 0

    persist_records(promoted)
    logger.info("Promoted %d session summaries to long-term memory.", len(promoted))
    return len(promoted)

