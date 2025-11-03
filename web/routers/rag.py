"""FastAPI routes for the Interactive Analyst (RAG) module."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.logging import get_logger
from database import SessionLocal, get_db
from llm import llm_service
from llm.guardrails import SAFE_MESSAGE
from parse.tasks import run_rag_self_check, snapshot_evidence_diff
from schemas.api.rag import (
    EvidenceAnchor,
    FilingFilter,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGEvidence,
    RelatedFiling,
    SelfCheckResult,
)
from services import chat_service, vector_service
from services.rag_shared import build_anchor_payload, normalize_reliability, safe_float, safe_int
from services.evidence_service import attach_diff_metadata
from models.chat import ChatMessage, ChatSession


def _extract_anchor(chunk: Dict[str, Any]) -> Optional[EvidenceAnchor]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    anchor_payload = build_anchor_payload(chunk, metadata)
    if not anchor_payload:
        return None
    allowed_keys = {"paragraph_id", "pdf_rect", "similarity"}
    filtered = {key: anchor_payload.get(key) for key in allowed_keys if key in anchor_payload}
    if not filtered:
        return None
    return EvidenceAnchor.model_validate(filtered)


def _normalize_self_check(value: Any) -> Optional[SelfCheckResult]:
    if not isinstance(value, dict):
        return None
    score = safe_float(value.get("score"))
    verdict_raw = value.get("verdict")
    verdict = verdict_raw.strip().lower() if isinstance(verdict_raw, str) else None
    if verdict and verdict not in {"pass", "warn", "fail"}:
        verdict = None
    payload: Dict[str, Any] = {}
    if score is not None:
        payload["score"] = max(0.0, min(1.0, score))
    if verdict:
        payload["verdict"] = verdict
    if isinstance(value.get("explanation"), str):
        payload["explanation"] = value["explanation"]
    if not payload:
        return None
    return SelfCheckResult.model_validate(payload)


def _resolve_urn(chunk: Dict[str, Any], *, chunk_id: Optional[str]) -> str:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    urn_value = chunk.get("urn_id") or metadata.get("urn_id")
    if urn_value:
        return str(urn_value)
    if chunk_id:
        return f"urn:chunk:{chunk_id}"
    content = chunk.get("content") or metadata.get("content") or ""
    base = str(content)[:128] if content else json.dumps(chunk, sort_keys=True)[:128]
    deterministic = uuid.uuid5(uuid.NAMESPACE_URL, base)
    return f"urn:chunk:{deterministic}"


def _build_evidence_payload(chunks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        chunk_id_raw = chunk.get("chunk_id") or chunk.get("id") or metadata.get("chunk_id")
        chunk_id = str(chunk_id_raw) if chunk_id_raw is not None else None
        page_number = metadata.get("page_number") or chunk.get("page_number")
        section = metadata.get("section") or chunk.get("section")
        quote = metadata.get("quote") or chunk.get("quote") or chunk.get("content") or ""
        anchor = _extract_anchor(chunk)
        self_check = _normalize_self_check(chunk.get("self_check") or metadata.get("self_check"))
        reliability = normalize_reliability(
            chunk.get("source_reliability") or metadata.get("source_reliability")
        )
        created_at = metadata.get("created_at") or chunk.get("created_at")

        evidence_model = RAGEvidence(
            urn_id=_resolve_urn(chunk, chunk_id=chunk_id),
            chunk_id=chunk_id,
            page_number=safe_int(page_number),
            section=section,
            quote=str(quote) if quote is not None else "",
            content=str(quote) if quote is not None else None,
            anchor=anchor,
            self_check=self_check,
            source_reliability=reliability,
            created_at=created_at,
        )
        evidence.append(
            evidence_model.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        )
    return evidence


def _attach_evidence_diff(
    evidence: List[Dict[str, Any]],
    *,
    db: Optional[Session] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not evidence:
        return evidence, {"enabled": False, "removed": []}

    session = db
    owns_session = False
    if session is None:
        session = SessionLocal()
        owns_session = True
    try:
        meta = attach_diff_metadata(session, evidence) or {}
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


def _enqueue_evidence_snapshot(
    evidence: List[Dict[str, Any]],
    *,
    author: Optional[str],
    trace_id: str,
    process: str = "api.rag.query",
) -> None:
    if not evidence:
        return
    try:
        snapshot_evidence_diff.delay(
            {
                "trace_id": trace_id,
                "author": author,
                "process": process,
                "evidence": evidence,
            }
        )
    except Exception as exc:  # pragma: no cover - fire-and-forget
        logger.warning("Failed to enqueue evidence snapshot (trace_id=%s): %s", trace_id, exc, exc_info=True)


logger = get_logger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])

NO_CONTEXT_ANSWER = "관련 근거 문서를 찾지 못했습니다. 다른 질문을 시도해 주세요."
INTENT_GENERAL_MESSAGE = "저는 공시·금융 뉴스 정보를 기반으로 답변하는 서비스입니다. 관련된 질문을 입력해 주세요."
INTENT_BLOCK_MESSAGE = SAFE_MESSAGE
INTENT_WARNING_CODE = "intent_filter"


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID header.") from exc

def _coerce_uuid(value, *, default=None):
    """Convert an arbitrary identifier to a UUID."""
    if isinstance(value, uuid.UUID):
        return value
    if value is not None:
        value_str = str(value)
        try:
            return uuid.UUID(value_str)
        except ValueError:
            return uuid.uuid5(uuid.NAMESPACE_URL, value_str)
    return default or uuid.uuid4()



def _parse_iso_timestamp(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        normalized = value.strip()
        if normalized.endswith('Z'):
            normalized = normalized[:-1] + '+00:00'
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()



def _prepare_vector_filters(filters: FilingFilter) -> Dict[str, Any]:
    raw = filters.model_dump(exclude_none=True)
    vector_filters: Dict[str, Any] = {}
    for key in ('ticker', 'sector', 'sentiment'):
        value = raw.get(key)
        if value:
            vector_filters[key] = value
    min_ts = _parse_iso_timestamp(raw.get('min_published_at'))
    max_ts = _parse_iso_timestamp(raw.get('max_published_at'))
    if min_ts is not None:
        vector_filters['min_published_at_ts'] = min_ts
    if max_ts is not None:
        vector_filters['max_published_at_ts'] = max_ts
    return vector_filters



def _guard_session_owner(session: ChatSession, user_id: Optional[uuid.UUID], org_id: Optional[uuid.UUID]) -> None:
    if session.archived_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session archived.")
    if session.user_id and user_id and session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden session access.")
    if session.org_id and org_id and session.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden session access.")


def _vector_search(
    question: str,
    *,
    filing_id: Optional[str],
    top_k: int,
    max_filings: int,
    filters: Dict[str, Any],
) -> vector_service.VectorSearchResult:
    try:
        return vector_service.query_vector_store(
            query_text=question,
            filing_id=filing_id,
            top_k=top_k,
            max_filings=max_filings,
            filters=filters,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Vector search failed (filing=%s): %s", filing_id or "<auto>", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="Vector search is currently unavailable.")


def build_empty_response(
    db: Session,
    *,
    question: str,
    filing_id: Optional[str],
    trace_id: str,
    session: ChatSession,
    turn_id: uuid.UUID,
    user_message: ChatMessage,
    assistant_message: ChatMessage,
    conversation_memory: Optional[Dict[str, Any]] = None,
    related_filings: Optional[List[RelatedFiling]] = None,
    judge_result: Optional[Dict[str, Any]] = None,
    rag_mode: str = "vector",
) -> Tuple[RAGQueryResponse, bool]:
    fallback_text = NO_CONTEXT_ANSWER
    conversation_summary = None
    recent_turns = 0
    if conversation_memory:
        conversation_summary = conversation_memory.get("summary")
        recent_turns = len(conversation_memory.get("recent_turns") or [])
    guardrail_meta = {
        "decision": judge_result.get("decision") if judge_result else None,
        "reason": judge_result.get("reason") if judge_result else None,
        "rag_mode": rag_mode,
    }
    meta_payload = {
        "model": None,
        "prompt_version": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "cost": None,
        "retrieval": {"doc_ids": [], "hit_at_k": 0, "filing_id": None, "filters": {}},
        "guardrail": guardrail_meta,
        "turnId": str(turn_id),
        "traceId": trace_id,
        "citations": {"page": [], "table": [], "footnote": []},
        "conversation_summary": conversation_summary,
        "recent_turn_count": recent_turns,
        "answer_preview": chat_service.trim_preview(fallback_text),
        "selected_filing_id": filing_id,
    }
    meta_payload["evidence_version"] = "v2"
    meta_payload["evidence_diff"] = {"enabled": False, "removed": []}
    chat_service.update_message_state(
        db,
        message_id=assistant_message.id,
        state="ready",
        content=fallback_text,
        meta=meta_payload,
    )
    needs_summary = chat_service.should_trigger_summary(db, session)
    response = RAGQueryResponse(
        question=question,
        filing_id=filing_id,
        session_id=session.id,
        turn_id=turn_id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        answer=fallback_text,
        context=[],
        citations={},
        warnings=["no_context"],
        highlights=[],
        error=None,
        original_answer=None,
        model_used=None,
        trace_id=trace_id,
        meta=meta_payload,
        state="ready",
        related_filings=related_filings or [],
        rag_mode=rag_mode,
    )
    return response, needs_summary


def build_intent_reply(
    db: Session,
    *,
    question: str,
    trace_id: str,
    session: ChatSession,
    turn_id: uuid.UUID,
    user_message: ChatMessage,
    assistant_message: ChatMessage,
    decision: str,
    reason: Optional[str],
    model_used: Optional[str],
    conversation_memory: Optional[Dict[str, Any]] = None,
) -> Tuple[RAGQueryResponse, bool]:
    answer_text = INTENT_GENERAL_MESSAGE if decision == "semi_pass" else INTENT_BLOCK_MESSAGE
    warning_code = f"{INTENT_WARNING_CODE}:{decision}"
    warnings = [warning_code]
    error_code = warning_code if decision == "block" else None
    state_value = "error" if decision == "block" else "ready"
    conversation_summary = None
    recent_turn_count = 0
    if conversation_memory:
        conversation_summary = conversation_memory.get("summary")
        recent_turn_count = len(conversation_memory.get("recent_turns") or [])

    meta_payload = {
        "model": model_used,
        "prompt_version": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "cost": None,
        "retrieval": {"doc_ids": [], "hit_at_k": 0},
        "guardrail": {"decision": warning_code, "reason": reason},
        "turnId": str(turn_id),
        "traceId": trace_id,
        "citations": {"page": [], "table": [], "footnote": []},
        "conversation_summary": conversation_summary,
        "recent_turn_count": recent_turn_count,
        "answer_preview": chat_service.trim_preview(answer_text),
        "intent_decision": decision,
        "intent_reason": reason,
        "selected_filing_id": None,
        "related_filings": [],
    }
    meta_payload["evidence_version"] = "v2"
    meta_payload["evidence_diff"] = {"enabled": False, "removed": []}
    meta_payload["guardrail"]["rag_mode"] = "none"

    chat_service.update_message_state(
        db,
        message_id=assistant_message.id,
        state=state_value,
        error_code=error_code,
        error_message=reason if decision == "block" else None,
        content=answer_text,
        meta=meta_payload,
    )
    needs_summary = chat_service.should_trigger_summary(db, session)

    response = RAGQueryResponse(
        question=question,
        filing_id=None,
        session_id=session.id,
        turn_id=turn_id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        answer=answer_text,
        context=[],
        citations={},
        warnings=warnings,
        highlights=[],
        error=error_code,
        original_answer=None,
        model_used=model_used,
        trace_id=trace_id,
        judge_decision=None,
        judge_reason=reason,
        meta=meta_payload,
        state="blocked" if decision == "block" else "ready",
        related_filings=[],
        rag_mode="none",
    )

    return response, needs_summary


def build_basic_reply(
    *,
    question: str,
    filing_id: Optional[str],
    trace_id: str,
    top_k: int,
    run_self_check: bool,
    filters: Optional[Dict[str, Any]] = None,
) -> RAGQueryResponse:
    judge_result = llm_service.assess_query_risk(question)
    judge_decision = (judge_result.get("decision") or "unknown") if judge_result else "unknown"
    rag_mode = (judge_result.get("rag_mode") or "vector") if judge_result else "vector"

    should_retrieve = rag_mode != "none" and judge_decision in {"pass", "unknown"}
    retrieval: Optional[vector_service.VectorSearchResult] = None
    context_chunks: List[Dict[str, Any]] = []
    related_filings: List[RelatedFiling] = []
    selected_filing_id = filing_id

    if should_retrieve:
        retrieval = _vector_search(
            question,
            filing_id=filing_id,
            top_k=top_k,
            max_filings=1,
            filters=filters or {},
        )
        context_chunks = retrieval.chunks
        related_filings = [
            RelatedFiling(
                filing_id=item["filing_id"],
                score=float(item.get("score") or 0.0),
                title=item.get("title"),
                sentiment=item.get("sentiment"),
                published_at=item.get("published_at"),
            )
            for item in retrieval.related_filings
            if item.get("filing_id")
        ]
        selected_filing_id = retrieval.filing_id or filing_id
        if selected_filing_id is None and related_filings:
            selected_filing_id = related_filings[0].filing_id

        if rag_mode == "vector" and not context_chunks:
            return RAGQueryResponse(
                question=question,
                filing_id=selected_filing_id,
                session_id=None,
                turn_id=None,
                user_message_id=None,
                assistant_message_id=None,
                answer=NO_CONTEXT_ANSWER,
                context=[],
                citations={},
                warnings=["no_context"],
                highlights=[],
                error=None,
                original_answer=None,
                model_used=None,
                trace_id=trace_id,
                meta={
                    "selected_filing_id": selected_filing_id,
                    "related_filings": [item.model_dump() for item in related_filings],
                    "evidence_version": "v2",
                    "evidence_diff": {"enabled": False, "removed": []},
                    "guardrail": {
                        "decision": judge_result.get("decision") if judge_result else None,
                        "reason": judge_result.get("reason") if judge_result else None,
                        "rag_mode": rag_mode,
                    },
                },
                state="ready",
                related_filings=related_filings,
                rag_mode=rag_mode,
            )

    payload = llm_service.generate_rag_answer(question, context_chunks, judge_result=judge_result)
    payload_rag_mode = payload.get("rag_mode") or rag_mode
    meta_payload = dict(payload.get("meta", {}))
    retrieval_meta = dict(meta_payload.get("retrieval") or {})
    retrieval_meta.setdefault("filing_id", selected_filing_id)
    retrieval_meta.setdefault("rag_mode", payload_rag_mode)
    meta_payload["retrieval"] = retrieval_meta
    meta_payload.setdefault("selected_filing_id", selected_filing_id)
    meta_payload.setdefault("related_filings", [item.model_dump() for item in related_filings])
    guard_meta = dict(meta_payload.get("guardrail") or {})
    guard_meta.setdefault("decision", payload.get("judge_decision"))
    guard_meta.setdefault("reason", payload.get("judge_reason"))
    guard_meta["rag_mode"] = payload_rag_mode
    meta_payload["guardrail"] = guard_meta

    evidence_context = _build_evidence_payload(payload.get("context") or context_chunks)
    snapshot_payload = deepcopy(evidence_context)
    evidence_context, diff_meta = _attach_evidence_diff(evidence_context)
    meta_payload.setdefault("evidence_version", "v2")
    meta_payload["evidence_diff"] = diff_meta

    response = RAGQueryResponse(
        question=question,
        filing_id=selected_filing_id,
        session_id=None,
        turn_id=None,
        user_message_id=None,
        assistant_message_id=None,
        answer=payload.get("answer", ""),
        context=evidence_context,
        citations=dict(payload.get("citations", {})),
        warnings=list(payload.get("warnings", [])),
        highlights=list(payload.get("highlights", [])),
        error=payload.get("error"),
        original_answer=payload.get("original_answer"),
        model_used=payload.get("model_used"),
        trace_id=trace_id,
        judge_decision=payload.get("judge_decision"),
        judge_reason=payload.get("judge_reason"),
        meta=meta_payload,
        state=payload.get("state", "ready"),
        related_filings=related_filings,
        rag_mode=payload_rag_mode,
    )

    if run_self_check:
        try:
            run_rag_self_check.delay(
                {
                    "question": question,
                    "filing_id": selected_filing_id,
                    "answer": response.model_dump(mode="json"),
                    "context": context_chunks,
                    "trace_id": trace_id,
                }
            )
        except Exception as exc:  # pragma: no cover - background task failure
            logger.warning("Failed to enqueue stateless RAG self-check (trace_id=%s): %s", trace_id, exc)

    if snapshot_payload:
        _enqueue_evidence_snapshot(
            snapshot_payload,
            author=None,
            trace_id=trace_id,
        )

    return response

def _resolve_session(
    db: Session,
    *,
    session_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    filing_id: Optional[str],
) -> ChatSession:
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id)
            .with_for_update()
            .first()
        )
        if session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        _guard_session_owner(session, user_id, org_id)
        if (
            filing_id
            and session.context_type == "filing"
            and session.context_id
            and session.context_id != filing_id
        ):
            logger.debug(
                "Session %s context filing mismatch (expected=%s, provided=%s). Continuing with existing context.",
                session.id,
                session.context_id,
                filing_id,
            )
        return session

    context_type = "filing" if filing_id else "corpus"
    session = chat_service.create_chat_session(
        db,
        user_id=user_id,
        org_id=org_id,
        title=None,
        context_type=context_type,
        context_id=filing_id,
    )
    return session


def _ensure_user_message(
    db: Session,
    *,
    session: ChatSession,
    user_message_id: Optional[uuid.UUID],
    question: str,
    turn_id: uuid.UUID,
    idempotency_key: Optional[str],
    meta: Dict[str, object],
) -> ChatMessage:
    if user_message_id:
        existing = (
            db.query(ChatMessage)
            .filter(ChatMessage.id == user_message_id, ChatMessage.session_id == session.id)
            .first()
        )
        if existing:
            return existing

    return chat_service.create_chat_message(
        db,
        message_id=user_message_id,
        session_id=session.id,
        role="user",
        content=question,
        turn_id=turn_id,
        idempotency_key=idempotency_key,
        meta=meta,
        state="ready",
    )


def _ensure_assistant_message(
    db: Session,
    *,
    session: ChatSession,
    assistant_message_id: Optional[uuid.UUID],
    turn_id: uuid.UUID,
    idempotency_key: Optional[str],
    retry_of_message_id: Optional[uuid.UUID],
    initial_state: str,
) -> ChatMessage:
    if assistant_message_id:
        existing = (
            db.query(ChatMessage)
            .filter(ChatMessage.id == assistant_message_id, ChatMessage.session_id == session.id)
            .first()
        )
        if existing:
            return existing

    return chat_service.create_chat_message(
        db,
        message_id=assistant_message_id,
        session_id=session.id,
        role="assistant",
        content=None,
        turn_id=turn_id,
        idempotency_key=idempotency_key,
        retry_of_message_id=retry_of_message_id,
        meta={},
        state=initial_state,
    )




@router.post("/query", response_model=RAGQueryResponse)
def query_rag(
    request: RAGQueryRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    idempotency_key_header: Optional[str] = Header(default=None, convert_underscores=False, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> RAGQueryResponse:
    question = request.question.strip()
    filing_id = request.filing_id.strip() if request.filing_id else None
    filter_payload = _prepare_vector_filters(request.filters)
    max_filings = request.max_filings
    trace_id = str(uuid.uuid4())

    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    turn_id = _coerce_uuid(request.turn_id)
    idempotency_key = request.idempotency_key or idempotency_key_header

    user_meta = dict(request.meta or {})

    try:
        session = _resolve_session(
            db,
            session_id=request.session_id,
            user_id=user_id,
            org_id=org_id,
            filing_id=filing_id,
        )
        user_message = _ensure_user_message(
            db,
            session=session,
            user_message_id=request.user_message_id,
            question=question,
            turn_id=turn_id,
            idempotency_key=idempotency_key,
            meta=user_meta,
        )
        assistant_message = _ensure_assistant_message(
            db,
            session=session,
            assistant_message_id=request.assistant_message_id,
            turn_id=turn_id,
            idempotency_key=None,
            retry_of_message_id=request.retry_of_message_id,
            initial_state="pending",
        )

        conversation_memory = chat_service.build_conversation_memory(db, session)
        intent_result = llm_service.classify_query_intent(question)
        intent_decision = (intent_result.get("decision") or "pass").lower()
        intent_reason = intent_result.get("reason")
        intent_model = intent_result.get("model_used")

        if intent_decision != "pass":
            response, needs_summary = build_intent_reply(
                db,
                question=question,
                trace_id=trace_id,
                session=session,
                turn_id=turn_id,
                user_message=user_message,
                assistant_message=assistant_message,
                decision=intent_decision,
                reason=intent_reason,
                model_used=intent_model,
                conversation_memory=conversation_memory,
            )
            db.commit()
            if needs_summary:
                chat_service.enqueue_session_summary(session.id)
            return response

        judge_result = llm_service.assess_query_risk(question)
        judge_decision = (judge_result.get("decision") or "unknown") if judge_result else "unknown"
        rag_mode = (judge_result.get("rag_mode") or "vector") if judge_result else "vector"

        should_retrieve = rag_mode != "none" and judge_decision in {"pass", "unknown"}
        retrieval: Optional[vector_service.VectorSearchResult] = None
        context_chunks: List[Dict[str, Any]] = []
        related_filings: List[RelatedFiling] = []
        active_filing_id = filing_id

        if should_retrieve:
            retrieval = _vector_search(
                question,
                filing_id=filing_id,
                top_k=request.top_k,
                max_filings=max_filings,
                filters=filter_payload,
            )
            context_chunks = retrieval.chunks
            related_filings = [
                RelatedFiling(
                    filing_id=item["filing_id"],
                    score=float(item.get("score") or 0.0),
                    title=item.get("title"),
                    sentiment=item.get("sentiment"),
                    published_at=item.get("published_at"),
                )
                for item in retrieval.related_filings
                if item.get("filing_id")
            ]
            active_filing_id = retrieval.filing_id or filing_id
            if active_filing_id is None and related_filings:
                active_filing_id = related_filings[0].filing_id

            if rag_mode == "vector" and not context_chunks:
                logger.info("No context chunks found (filing=%s, trace_id=%s).", active_filing_id or "<auto>", trace_id)
                response, needs_summary = build_empty_response(
                    db,
                    question=question,
                    filing_id=active_filing_id,
                    trace_id=trace_id,
                    session=session,
                    turn_id=turn_id,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    conversation_memory=conversation_memory,
                    related_filings=related_filings,
                )
                db.commit()
                if needs_summary:
                    chat_service.enqueue_session_summary(session.id)
                return response

        selected_filing_id = active_filing_id
        started_at = datetime.now(timezone.utc)
        result = llm_service.generate_rag_answer(question, context_chunks, judge_result=judge_result)
        payload_rag_mode = result.get("rag_mode") or rag_mode
        latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

        error = result.get("error")
        if error and not (
            str(error).startswith("missing_citations") or str(error).startswith("guardrail_violation")
        ):
            chat_service.update_message_state(
                db,
                message_id=assistant_message.id,
                state="error",
                error_code="llm_error",
                error_message=str(error),
                meta={"latency_ms": latency_ms},
            )
            db.commit()
            raise HTTPException(status_code=500, detail=f"LLM answer failed: {error}")

        context = _build_evidence_payload(result.get("context") or context_chunks)
        snapshot_payload = deepcopy(context)
        context, diff_meta = _attach_evidence_diff(context, db=db)
        citations: Dict[str, List[str]] = dict(result.get("citations") or {})
        warnings: List[str] = list(result.get("warnings") or [])
        highlights: List[Dict[str, object]] = list(result.get("highlights") or [])

        retrieval_ids = [chunk.get("id") for chunk in context_chunks if isinstance(chunk.get("id"), str)]
        answer_text = result.get("answer", "지금은 답변을 준비할 수 없습니다.")
        state_value = "error" if error else "ready"
        conversation_summary = None
        recent_turn_count = 0
        if conversation_memory:
            conversation_summary = conversation_memory.get("summary")
            recent_turn_count = len(conversation_memory.get("recent_turns") or [])
        meta_payload = {
            "model": result.get("model_used"),
            "prompt_version": request.meta.get("prompt_version") if isinstance(request.meta, dict) else None,
            "latency_ms": latency_ms,
            "input_tokens": request.meta.get("input_tokens") if isinstance(request.meta, dict) else None,
            "output_tokens": request.meta.get("output_tokens") if isinstance(request.meta, dict) else None,
            "cost": request.meta.get("cost") if isinstance(request.meta, dict) else None,
            "retrieval": {
                "doc_ids": retrieval_ids,
                "hit_at_k": len(context_chunks),
                "filing_id": selected_filing_id,
                "filters": filter_payload,
                "rag_mode": payload_rag_mode,
            },
            "guardrail": {
                "decision": result.get("judge_decision"),
                "reason": result.get("judge_reason"),
                "rag_mode": payload_rag_mode,
            },
            "turnId": str(turn_id),
            "traceId": trace_id,
            "citations": citations,
            "conversation_summary": conversation_summary,
            "recent_turn_count": recent_turn_count,
            "answer_preview": chat_service.trim_preview(answer_text),
            "selected_filing_id": selected_filing_id,
            "related_filings": [item.model_dump() for item in related_filings],
            "intent_decision": intent_decision,
            "intent_reason": intent_reason,
            "intent_model": intent_result.get("model_used"),
        }
        meta_payload["evidence_version"] = "v2"
        meta_payload["evidence_diff"] = diff_meta
        chat_service.update_message_state(
            db,
            message_id=assistant_message.id,
            state=state_value,
            error_code=error if error else None,
            error_message=error if error else None,
            content=answer_text,
            meta=meta_payload,
        )
        needs_summary = chat_service.should_trigger_summary(db, session)

        response = RAGQueryResponse(
            question=question,
            filing_id=selected_filing_id,
            session_id=session.id,
            turn_id=turn_id,
            user_message_id=user_message.id,
            assistant_message_id=assistant_message.id,
            answer=answer_text,
            context=context,
            citations=citations,
            warnings=warnings,
            highlights=highlights,
            error=error,
            original_answer=result.get("original_answer"),
            model_used=result.get("model_used"),
            trace_id=trace_id,
            judge_decision=result.get("judge_decision"),
            judge_reason=result.get("judge_reason"),
            meta=meta_payload,
            state=state_value,
            related_filings=related_filings,
            rag_mode=payload_rag_mode,
        )

        if request.run_self_check:
            payload = {
                "question": question,
                "filing_id": selected_filing_id,
                "answer": response.model_dump(mode="json"),
                "context": context_chunks,
                "trace_id": trace_id,
            }
            try:
                run_rag_self_check.delay(payload)
            except Exception as exc:  # pragma: no cover - background task failure
                logger.warning(
                    "Failed to enqueue RAG self-check (trace_id=%s): %s", trace_id, exc, exc_info=True
                )

        snapshot_author = None
        if user_id:
            snapshot_author = str(user_id)
        elif session.user_id:
            snapshot_author = str(session.user_id)
        if snapshot_payload:
            _enqueue_evidence_snapshot(
                snapshot_payload,
                author=snapshot_author,
                trace_id=trace_id,
            )

        db.commit()
        if needs_summary:
            chat_service.enqueue_session_summary(session.id)
        return response
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning("Database error during RAG query; falling back to stateless mode: %s", exc)
        return build_basic_reply(
            question=question,
            filing_id=filing_id,
            trace_id=trace_id,
            top_k=request.top_k,
            run_self_check=request.run_self_check,
            filters=filter_payload,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/query/stream")
def query_rag_stream(
    request: RAGQueryRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    idempotency_key_header: Optional[str] = Header(default=None, convert_underscores=False, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    question = request.question.strip()
    filing_id = request.filing_id.strip() if request.filing_id else None
    filter_payload = _prepare_vector_filters(request.filters)
    max_filings = request.max_filings
    trace_id = str(uuid.uuid4())

    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    turn_id = _coerce_uuid(request.turn_id)
    idempotency_key = request.idempotency_key or idempotency_key_header

    try:
        session = _resolve_session(
            db,
            session_id=request.session_id,
            user_id=user_id,
            org_id=org_id,
            filing_id=filing_id,
        )
        user_message = _ensure_user_message(
            db,
            session=session,
            user_message_id=request.user_message_id,
            question=question,
            turn_id=turn_id,
            idempotency_key=idempotency_key,
            meta=request.meta or {},
        )
        assistant_message = _ensure_assistant_message(
            db,
            session=session,
            assistant_message_id=request.assistant_message_id,
            turn_id=turn_id,
            idempotency_key=None,
            retry_of_message_id=request.retry_of_message_id,
            initial_state="pending",
        )
        conversation_memory = chat_service.build_conversation_memory(db, session)
        intent_result = llm_service.classify_query_intent(question)
        intent_decision = (intent_result.get("decision") or "pass").lower()
        intent_reason = intent_result.get("reason")
        intent_model = intent_result.get("model_used")

        if intent_decision != "pass":
            response, needs_summary = build_intent_reply(
                db,
                question=question,
                trace_id=trace_id,
                session=session,
                turn_id=turn_id,
                user_message=user_message,
                assistant_message=assistant_message,
                decision=intent_decision,
                reason=intent_reason,
                model_used=intent_model,
                conversation_memory=conversation_memory,
            )
            db.commit()
            if needs_summary:
                chat_service.enqueue_session_summary(session.id)

            payload_json = response.model_dump(mode="json")

            def intent_stream():
                yield json.dumps(
                    {
                        "event": "done",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "payload": payload_json,
                    }
                ) + "\n"

            return StreamingResponse(intent_stream(), media_type="text/event-stream")

        judge_result = llm_service.assess_query_risk(question)
        judge_decision = (judge_result.get("decision") or "unknown") if judge_result else "unknown"
        rag_mode = (judge_result.get("rag_mode") or "vector") if judge_result else "vector"

        should_retrieve = rag_mode != "none" and judge_decision in {"pass", "unknown"}
        retrieval: Optional[vector_service.VectorSearchResult] = None
        context_chunks: List[Dict[str, Any]] = []
        related_filings: List[RelatedFiling] = []
        active_filing_id = filing_id

        if should_retrieve:
            retrieval = _vector_search(
                question,
                filing_id=filing_id,
                top_k=request.top_k,
                max_filings=max_filings,
                filters=filter_payload,
            )
            context_chunks = retrieval.chunks
            related_filings = [
                RelatedFiling(
                    filing_id=item["filing_id"],
                    score=float(item.get("score") or 0.0),
                    title=item.get("title"),
                    sentiment=item.get("sentiment"),
                    published_at=item.get("published_at"),
                )
                for item in retrieval.related_filings
                if item.get("filing_id")
            ]
            active_filing_id = retrieval.filing_id or filing_id
            if active_filing_id is None and related_filings:
                active_filing_id = related_filings[0].filing_id

            if rag_mode == "vector" and not context_chunks:
                response, needs_summary = build_empty_response(
                    db,
                    question=question,
                    filing_id=active_filing_id,
                    trace_id=trace_id,
                    session=session,
                    turn_id=turn_id,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    conversation_memory=conversation_memory,
                    related_filings=related_filings,
                    judge_result=judge_result,
                    rag_mode=rag_mode,
                )
                db.commit()
                if needs_summary:
                    chat_service.enqueue_session_summary(session.id)

                payload = response.model_dump(mode="json")

                def no_context_stream():
                    yield json.dumps(
                        {
                            "event": "done",
                            "id": str(assistant_message.id),
                            "turn_id": str(turn_id),
                            "payload": payload,
                        }
                    ) + "\n"

                return StreamingResponse(no_context_stream(), media_type="text/event-stream")

        memory_summary = conversation_memory.get("summary") if conversation_memory else None
        memory_turn_count = len(conversation_memory.get("recent_turns") or []) if conversation_memory else 0
        selected_filing_id = active_filing_id
        related_meta = [item.model_dump() for item in related_filings]

        def event_stream():
            streamed_tokens: List[str] = []
            started_at = datetime.now(timezone.utc)
            initial_meta = {
                "trace_id": trace_id,
                "selected_filing_id": selected_filing_id,
                "related_filings": related_meta,
                "filters": filter_payload,
                "guardrail": {
                    "decision": judge_result.get("decision") if judge_result else None,
                    "reason": judge_result.get("reason") if judge_result else None,
                    "rag_mode": rag_mode,
                },
            }
            yield json.dumps(
                {
                    "event": "metadata",
                    "id": str(assistant_message.id),
                    "turn_id": str(turn_id),
                    "meta": initial_meta,
                }
            ) + "\n"

            final_payload: Optional[Dict[str, object]] = None
            try:
                for event in llm_service.stream_rag_answer(
                    question,
                    context_chunks,
                    judge_result=judge_result,
                ):
                    if event.get("type") == "token":
                        token = event.get("text") or ""
                        if token:
                            streamed_tokens.append(token)
                            yield json.dumps(
                                {
                                    "event": "chunk",
                                    "id": str(assistant_message.id),
                                    "turn_id": str(turn_id),
                                    "delta": token,
                                }
                            ) + "\n"
                    elif event.get("type") == "final":
                        final_payload = event.get("payload") or {}
                    elif event.get("type") == "error":
                        raise RuntimeError(event.get("message") or "Streaming error")

                if final_payload is None:
                    final_payload = {}

                payload_rag_mode = final_payload.get("rag_mode") or rag_mode

                answer_text = final_payload.get("answer") or "".join(streamed_tokens) or "지금은 답변을 준비할 수 없습니다."
                context = _build_evidence_payload(final_payload.get("context") or context_chunks)
                snapshot_payload = deepcopy(context)
                context, diff_meta = _attach_evidence_diff(context, db=db)
                citations: Dict[str, List[str]] = dict(final_payload.get("citations") or {})
                warnings: List[str] = list(final_payload.get("warnings") or [])
                highlights: List[Dict[str, object]] = list(final_payload.get("highlights") or [])
                error = final_payload.get("error")

                latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
                retrieval_ids = [chunk.get("id") for chunk in context_chunks if isinstance(chunk.get("id"), str)]
                meta_payload = {
                    "model": final_payload.get("model_used"),
                    "prompt_version": request.meta.get("prompt_version") if isinstance(request.meta, dict) else None,
                    "latency_ms": latency_ms,
                    "input_tokens": request.meta.get("input_tokens") if isinstance(request.meta, dict) else None,
                    "output_tokens": request.meta.get("output_tokens") if isinstance(request.meta, dict) else None,
                    "cost": request.meta.get("cost") if isinstance(request.meta, dict) else None,
                    "retrieval": {
                        "doc_ids": retrieval_ids,
                        "hit_at_k": len(context_chunks),
                        "filing_id": selected_filing_id,
                        "filters": filter_payload,
                        "rag_mode": payload_rag_mode,
                    },
                    "guardrail": {
                        "decision": final_payload.get("judge_decision"),
                        "reason": final_payload.get("judge_reason"),
                        "rag_mode": payload_rag_mode,
                    },
                    "turnId": str(turn_id),
                    "traceId": trace_id,
                    "citations": citations,
                    "conversation_summary": memory_summary,
                    "recent_turn_count": memory_turn_count,
                    "answer_preview": chat_service.trim_preview(answer_text),
                    "selected_filing_id": selected_filing_id,
                    "related_filings": related_meta,
                }
                meta_payload["evidence_version"] = "v2"
                meta_payload["evidence_diff"] = diff_meta

                state_value = "error" if error else "ready"
                chat_service.update_message_state(
                    db,
                    message_id=assistant_message.id,
                    state=state_value,
                    error_code=str(error) if error else None,
                    error_message=str(error) if error else None,
                    content=answer_text,
                    meta=meta_payload,
                )
                needs_summary = chat_service.should_trigger_summary(db, session)

                response = RAGQueryResponse(
                    question=question,
                    filing_id=selected_filing_id,
                    session_id=session.id,
                    turn_id=turn_id,
                    user_message_id=user_message.id,
                    assistant_message_id=assistant_message.id,
                    answer=answer_text,
                    context=context,
                    citations=citations,
                    warnings=warnings,
                    highlights=highlights,
                    error=error,
                    original_answer=final_payload.get("original_answer"),
                    model_used=final_payload.get("model_used"),
                    trace_id=trace_id,
                    judge_decision=final_payload.get("judge_decision"),
                    judge_reason=final_payload.get("judge_reason"),
                    meta=meta_payload,
                    state=state_value,
                    related_filings=related_filings,
                    rag_mode=payload_rag_mode,
                )

                if request.run_self_check:
                    try:
                        run_rag_self_check.delay(
                            {
                                "question": question,
                                "filing_id": selected_filing_id,
                                "answer": response.model_dump(mode="json"),
                                "context": context_chunks,
                                "trace_id": trace_id,
                            }
                        )
                    except Exception as exc:  # pragma: no cover - background task failure
                        logger.warning(
                            "Failed to enqueue RAG self-check (trace_id=%s): %s", trace_id, exc, exc_info=True
                        )

                snapshot_author = None
                if user_id:
                    snapshot_author = str(user_id)
                elif session.user_id:
                    snapshot_author = str(session.user_id)
                if snapshot_payload:
                    _enqueue_evidence_snapshot(
                        snapshot_payload,
                        author=snapshot_author,
                        trace_id=trace_id,
                    )

                db.commit()
                if needs_summary:
                    chat_service.enqueue_session_summary(session.id)

                yield json.dumps(
                    {
                        "event": "done",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "payload": response.model_dump(mode="json"),
                    }
                ) + "\n"
            except Exception as exc:  # pragma: no cover - streaming failure
                db.rollback()
                chat_service.update_message_state(
                    db,
                    message_id=assistant_message.id,
                    state="error",
                    error_code="stream_error",
                    error_message=str(exc),
                    meta={"turnId": str(turn_id), "traceId": trace_id},
                )
                db.commit()
                yield json.dumps(
                    {
                        "event": "error",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "message": str(exc),
                    }
                ) + "\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
__all__ = ["router"]




