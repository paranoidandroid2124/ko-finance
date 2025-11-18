"""Telemetry, LightMem, and evidence snapshot helpers for RAG workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.logging import get_logger
from database import SessionLocal
from services import chat_service, rag_jobs
from services.evidence_service import attach_diff_metadata
from services.memory.facade import MEMORY_SERVICE

logger = get_logger(__name__)


def telemetry_source(event: Any) -> str:
    source = None
    if isinstance(getattr(event, "source", None), str):
        source = event.source  # type: ignore[attr-defined]
    elif isinstance(getattr(event, "payload", None), dict):
        source = event.payload.get("source")
    if isinstance(source, str) and source.strip():
        return source.strip().lower()[:64]
    return "web"


def telemetry_reason(event_name: str, payload: Mapping[str, Any], failure_events: Iterable[str]) -> Optional[str]:
    if event_name not in set(failure_events):
        return None
    reason = payload.get("reason") or payload.get("error")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()[:128]
    return None


def telemetry_extra_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = {"reason", "error", "viewerVersion", "component", "device", "browser", "os"}
    extra = {}
    for key in allowed:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            extra[key] = value.strip()[:128]
    return extra


def merge_lightmem_context(
    question: str,
    conversation_memory: Optional[Dict[str, Any]],
    *,
    session_key: str,
    tenant_id: Optional[str],
    user_id: Optional[str],
    plan_memory_enabled: bool,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    info: Dict[str, Any] = {
        "enabled": MEMORY_SERVICE.is_enabled(plan_memory_enabled=plan_memory_enabled),
        "session_summaries": 0,
        "long_term_records": 0,
        "applied": False,
        "captured": False,
    }
    if not info["enabled"]:
        return conversation_memory, info
    if not tenant_id or not user_id:
        info["reason"] = "missing_subject"
        return conversation_memory, info

    snippets: List[str] = []
    base_memory = conversation_memory or {}
    recent_turns = base_memory.get("recent_turns") if isinstance(base_memory, dict) else None
    if isinstance(recent_turns, list):
        for turn in recent_turns[-3:]:
            if not isinstance(turn, dict):
                continue
            content = str(turn.get("content") or "").strip()
            if content:
                snippets.append(content)

    try:
        composition = MEMORY_SERVICE.compose_prompt(
            base_prompt=question,
            session_id=session_key,
            tenant_id=tenant_id,
            user_id=user_id,
            rag_snippets=snippets[:3],
            plan_memory_enabled=plan_memory_enabled,
        )
    except Exception:
        logger.debug("LightMem compose_prompt failed for session %s", session_key, exc_info=True)
        info["reason"] = "compose_failed"
        return conversation_memory, info

    info["session_summaries"] = len(composition.session_summaries)
    info["long_term_records"] = len(composition.long_term_records)
    info["compressed_chars"] = len(composition.compressed_prompt.text or "")

    summary_lines: List[str] = []
    for entry in composition.session_summaries:
        highlight = "; ".join(entry.highlights) if entry.highlights else ""
        text = f"{entry.topic}: {highlight}" if highlight else entry.topic
        line = text.strip()
        if line:
            summary_lines.append(line)
    for record in composition.long_term_records:
        topic = (record.topic or "").strip()
        summary = (record.summary or "").strip()
        if summary and topic:
            summary_lines.append(f"{topic}: {summary}")
        elif summary:
            summary_lines.append(summary)
        elif topic:
            summary_lines.append(topic)

    if not summary_lines:
        return conversation_memory, info

    merged: Dict[str, Any] = dict(base_memory) if isinstance(base_memory, dict) else {}
    existing_summary = (merged.get("summary") or "").strip()
    summary_parts: List[str] = []
    if existing_summary:
        summary_parts.extend(existing_summary.splitlines())
    seen_summary = {part.strip() for part in summary_parts if part.strip()}
    for line in summary_lines:
        if line not in seen_summary:
            summary_parts.append(line)
            seen_summary.add(line)
    if summary_parts:
        merged["summary"] = "\n".join(summary_parts)

    if composition.long_term_records:
        citations = list(merged.get("citations") or [])
        seen_citations = {str(item) for item in citations}
        for record in composition.long_term_records:
            topic = str(record.topic or "").strip()
            if topic and topic not in seen_citations:
                citations.append(topic)
                seen_citations.add(topic)
        if citations:
            merged["citations"] = citations

    info["applied"] = True
    return merged, info


def store_lightmem_summary(
    *,
    question: str,
    answer: str,
    session,
    turn_id,
    session_key: str,
    tenant_id: Optional[str],
    user_id: Optional[str],
    plan_memory_enabled: bool,
    rag_mode: Optional[str],
    filing_id: Optional[str],
) -> bool:
    if not MEMORY_SERVICE.is_enabled(plan_memory_enabled=plan_memory_enabled):
        return False
    if not tenant_id or not user_id:
        return False

    question_preview = chat_service.trim_preview(question)
    answer_preview = chat_service.trim_preview(answer)
    highlights: List[str] = []
    if question_preview:
        highlights.append(f"Q: {question_preview}")
    if answer_preview:
        highlights.append(f"A: {answer_preview}")
    if not highlights:
        return False

    total_len = len(question_preview) + len(answer_preview)
    importance = 0.45 + min(total_len, 600) / 1000.0
    metadata: Dict[str, str] = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_uuid": str(session.id),
        "turn_id": str(turn_id),
        "importance_score": f"{min(0.95, importance):.2f}",
    }
    if session.context_type:
        metadata["context_type"] = str(session.context_type)
    if session.context_id:
        metadata["context_id"] = str(session.context_id)
    if filing_id:
        metadata["filing_id"] = str(filing_id)
    if rag_mode:
        metadata["rag_mode"] = str(rag_mode)

    try:
        MEMORY_SERVICE.save_session_summary(
            session_id=session_key,
            topic=f"chat.{session.context_type or 'rag'}",
            highlights=highlights,
            metadata=metadata,
        )
        return True
    except Exception:
        logger.debug("LightMem session summary capture failed for %s", session_key, exc_info=True)
        return False


def attach_evidence_diff(
    evidence: List[Dict[str, Any]],
    *,
    db: Optional[Session] = None,
    trace_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not evidence:
        return evidence, {"enabled": False, "removed": []}

    session = db
    owns_session = False
    if session is None:
        session = SessionLocal()
        owns_session = True
    try:
        meta = attach_diff_metadata(session, evidence, trace_id=trace_id) or {}
        meta.setdefault("enabled", False)
        meta.setdefault("removed", [])
        return evidence, meta
    except SQLAlchemyError as exc:
        logger.warning("Failed to attach evidence diff (db error): %s", exc)
    except Exception as exc:  # pragma: no cover - defensive best effort
        logger.warning("Failed to attach evidence diff: %s", exc, exc_info=True)
    finally:
        if owns_session and session is not None:
            session.close()
    return evidence, {"enabled": False, "removed": []}


def build_citation_stats(citations: Mapping[str, Any]) -> Dict[str, Any]:
    total = 0
    with_offsets = 0
    with_hash = 0
    bucket_totals: Dict[str, int] = {}
    for bucket, entries in (citations or {}).items():
        if not isinstance(entries, list):
            continue
        bucket_count = 0
        for entry in entries:
            total += 1
            bucket_count += 1
            try:
                data = entry if isinstance(entry, dict) else json.loads(str(entry))
            except json.JSONDecodeError:
                continue
            if data.get("offsets"):
                with_offsets += 1
            if data.get("hash"):
                with_hash += 1
        if bucket_count:
            bucket_totals[bucket] = bucket_count
    return {
        "total": total,
        "with_offsets": with_offsets,
        "with_hash": with_hash,
        "buckets": bucket_totals,
    }


def enqueue_evidence_snapshot(
    evidence: List[Dict[str, Any]],
    *,
    author: Optional[str],
    trace_id: str,
    process: str = "api.rag.query",
    org_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
) -> None:
    if not evidence:
        return
    enriched: List[Dict[str, Any]] = []
    for entry in evidence:
        if not isinstance(entry, dict):
            continue
        copy_entry = dict(entry)
        copy_entry.setdefault("trace_id", trace_id)
        enriched.append(copy_entry)
    if not enriched:
        return
    rag_jobs.enqueue_evidence_snapshot(
        enriched,
        trace_id=trace_id,
        author=author,
        process=process,
        org_id=str(org_id) if org_id else None,
        user_id=str(user_id) if user_id else None,
    )


__all__ = [
    "telemetry_source",
    "telemetry_reason",
    "telemetry_extra_payload",
    "merge_lightmem_context",
    "store_lightmem_summary",
    "attach_evidence_diff",
    "build_citation_stats",
    "enqueue_evidence_snapshot",
]
