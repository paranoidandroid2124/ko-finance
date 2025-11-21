"""Telemetry, LightMem, and evidence snapshot helpers for RAG workflows."""

from __future__ import annotations

import json
import re
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
from services.memory.models import SessionSummaryEntry

logger = get_logger(__name__)

_KOSPI_TICKER_PATTERN = re.compile(r"\b\d{6}\b")
_ALPHA_TICKER_PATTERN = re.compile(r"\b[a-zA-Z]{1,5}\b")
_SECTOR_PATTERN = re.compile(r"([가-힣A-Za-z]{2,20})(?:\s*(?:섹터|산업|업종|리스크|위험))")
_MAX_PROFILE_HIGHLIGHTS = 5
_PROFILE_TOPIC = "profile.interest"


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


def _extract_interest_tokens(*texts: str, limit: int = _MAX_PROFILE_HIGHLIGHTS) -> List[str]:
    tokens: List[str] = []
    seen: set[str] = set()
    for text in texts:
        if not isinstance(text, str):
            continue
        for match in _KOSPI_TICKER_PATTERN.findall(text):
            if match not in seen:
                tokens.append(match)
                seen.add(match)
            if len(tokens) >= limit:
                return tokens
        for match in _ALPHA_TICKER_PATTERN.findall(text):
            cleaned = match.upper()
            if len(cleaned) < 2 or len(cleaned) > 5:
                continue
            if cleaned not in seen:
                tokens.append(cleaned)
                seen.add(cleaned)
            if len(tokens) >= limit:
                return tokens
    return tokens[:limit]


def _extract_sector_risk(text: str, limit: int = _MAX_PROFILE_HIGHLIGHTS) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    matches = []
    seen: set[str] = set()
    for match in _SECTOR_PATTERN.findall(text):
        normalized = match.strip()
        if not normalized or normalized in seen:
            continue
        matches.append(normalized)
        seen.add(normalized)
        if len(matches) >= limit:
            break
    return matches


def capture_user_interest_profile(
    *,
    question: str,
    answer: str,
    session,
    tenant_id: Optional[str],
    user_id: Optional[str],
    plan_memory_enabled: bool,
) -> bool:
    """Store a lightweight interest/profile hint for the user (hidden personalization)."""

    if not MEMORY_SERVICE.is_enabled(plan_memory_enabled=plan_memory_enabled, profile_context=True):
        return False
    if not tenant_id or not user_id:
        return False

    tokens = _extract_interest_tokens(question, answer)
    sectors = _extract_sector_risk(question + " " + answer)
    highlights: List[str] = []
    if tokens:
        highlights.append("관심 티커: " + ", ".join(tokens))
    if sectors:
        highlights.append("관심 산업/리스크: " + ", ".join(sectors))
    question_preview = chat_service.trim_preview(question)
    if question_preview:
        highlights.append(f"최근 질문: {question_preview}")
    if not highlights:
        return False

    metadata = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_uuid": str(session.id),
        "context_type": str(session.context_type or ""),
        "context_id": str(session.context_id or ""),
        "kind": "user_profile",
    }
    try:
        MEMORY_SERVICE.save_session_summary(
            session_id=f"user:{user_id}",
            topic=_PROFILE_TOPIC,
            highlights=highlights[: _MAX_PROFILE_HIGHLIGHTS],
            metadata=metadata,
            expires_at=MEMORY_SERVICE.profile_expiry(),
        )
        return True
    except Exception:
        logger.debug("User interest capture failed (user=%s)", user_id, exc_info=True)
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
