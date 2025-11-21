"""Celery task helpers for RAG workflows."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.logging import get_logger

try:  # pragma: no cover - celery unavailable in some test envs
    from parse.tasks import run_rag_self_check, snapshot_evidence_diff, run_snapshot_company_task
except Exception:  # pragma: no cover - fallback when tasks missing
    run_rag_self_check = None  # type: ignore[assignment]
    snapshot_evidence_diff = None  # type: ignore[assignment]
    run_snapshot_company_task = None  # type: ignore[assignment]

logger = get_logger(__name__)


def enqueue_self_check(payload: Dict[str, Any]) -> None:
    """Enqueue the async self-check task if available."""

    if not run_rag_self_check:
        logger.debug("run_rag_self_check task unavailable; skipping enqueue.")
        return

    try:
        run_rag_self_check.delay(payload)
    except Exception as exc:  # pragma: no cover - celery failure
        logger.warning("Failed to enqueue RAG self-check (trace_id=%s): %s", payload.get("trace_id"), exc, exc_info=True)


def enqueue_evidence_snapshot(
    evidence: List[Dict[str, Any]],
    *,
    trace_id: str,
    author: Optional[str],
    process: str = "api.rag.query",
    org_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Enqueue the evidence snapshot diff task."""

    if not snapshot_evidence_diff or not evidence:
        if not snapshot_evidence_diff:
            logger.debug("snapshot_evidence_diff task unavailable; skipping enqueue.")
        return

    payload = {
        "trace_id": trace_id,
        "author": author,
        "process": process,
        "evidence": evidence,
        "org_id": org_id,
        "user_id": user_id,
    }
    try:
        snapshot_evidence_diff.delay(payload)
    except Exception as exc:  # pragma: no cover - fire-and-forget
        logger.warning("Failed to enqueue evidence snapshot (trace_id=%s): %s", trace_id, exc, exc_info=True)


__all__ = ["enqueue_self_check", "enqueue_evidence_snapshot"]
