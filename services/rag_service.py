"""Business logic helpers for the Interactive Analyst (RAG) module."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Mapping

from pydantic import BaseModel
from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.logging import get_logger
from llm import llm_service
from llm.guardrails import SAFE_MESSAGE
from schemas.api.rag import (
    EvidenceAnchor,
    FilingFilter,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGEvidence,
    RelatedFiling,
    RAGDeeplinkPayload,
    RAGTelemetryRequest,
    RAGTelemetryResponse,
    SelfCheckResult,
)
from schemas.api.rag_v2 import (
    RagGridJobResponse,
    RagGridRequest,
    RagGridResponse,
    RagQueryFiltersSchema,
    RagQueryRequest as RagQueryV2Request,
    RagQueryResponse as RagQueryV2Response,
    RagWarningSchema,
)
from schemas.router import RouteDecision, RouteAction
from services import (
    chat_service,
    date_range_parser,
    hybrid_search,
    lightmem_gate,
    deeplink_service,
    rag_jobs,
    rag_audit,
    rag_grid,
    rag_pipeline,
    vector_service,
)
from services.audit_log import audit_rag_event
from services.semantic_router import DEFAULT_ROUTER
from services.user_settings_service import UserLightMemSettings
from services.rag_shared import build_anchor_payload, normalize_reliability, safe_float, safe_int
from models.chat import ChatMessage, ChatSession
from services.memory.facade import MEMORY_SERVICE
from services.plan_service import PlanContext
import services.rag_metrics as rag_metrics
from services.quota_guard import evaluate_quota

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


_ALLOWED_TELEMETRY_EVENTS: Dict[str, str] = {
    "rag.deeplink_opened": "deeplink",
    "rag.deeplink_failed": "deeplink",
    "rag.deeplink_viewer_ready": "viewer",
    "rag.deeplink_viewer_error": "viewer",
    "rag.deeplink_viewer_original_opened": "viewer",
    "rag.deeplink_viewer_original_failed": "viewer",
    "rag.evidence_view": "evidence",
    "rag.evidence_diff_toggle": "evidence",
}
_FAILURE_EVENTS = {
    "rag.deeplink_failed",
    "rag.deeplink_viewer_error",
    "rag.deeplink_viewer_original_failed",
}


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


def _table_hint(metadata: Dict[str, Any], page_number: Optional[int]) -> Optional[Dict[str, Any]]:
    table_index = metadata.get("table_index")
    if table_index is None:
        return None
    try:
        table_index_int = int(table_index)
    except (TypeError, ValueError):
        return None
    page_value = metadata.get("page_number") or page_number
    try:
        page_number_int = int(page_value) if page_value is not None else None
    except (TypeError, ValueError):
        page_number_int = None
    row_index: Optional[int] = None
    cell_coordinates = metadata.get("cell_coordinates") or []
    if isinstance(cell_coordinates, list):
        for cell in cell_coordinates:
            if not isinstance(cell, dict):
                continue
            try:
                row_candidate = int(cell.get("row"))
            except (TypeError, ValueError):
                row_candidate = None
            if row_candidate is None:
                continue
            if row_index is None or row_candidate < row_index:
                row_index = row_candidate
    return {
        "table_index": table_index_int,
        "page_number": page_number_int,
        "focus_row_index": row_index,
    }


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
        filing_id = chunk.get("filing_id") or metadata.get("filing_id")
        receipt_no = metadata.get("receipt_no") or chunk.get("receipt_no")
        viewer_url = metadata.get("viewer_url") or chunk.get("viewer_url")
        download_url = metadata.get("download_url") or chunk.get("download_url")
        document_url = metadata.get("document_url") or chunk.get("document_url") or viewer_url or download_url
        document_title = metadata.get("title") or chunk.get("title")

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
            filing_id=str(filing_id) if filing_id else None,
            receipt_no=str(receipt_no) if receipt_no else None,
            document_url=document_url,
            download_url=download_url,
            viewer_url=viewer_url,
            document_title=document_title,
        )
        entry = evidence_model.model_dump(mode="json", exclude_none=True, exclude_unset=True)
        table_hint = _table_hint(metadata, safe_int(page_number))
        if table_hint:
            entry["table_hint"] = table_hint
        evidence.append(entry)
    return evidence


def _plan_memory_enabled(
    plan: PlanContext,
    *,
    user_settings: Optional[UserLightMemSettings] = None,
) -> bool:
    return lightmem_gate.chat_enabled(plan, user_settings)


def _memory_subject_ids(
    session: ChatSession,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
) -> Tuple[Optional[str], Optional[str]]:
    tenant_candidate = org_id or session.org_id or session.user_id or user_id
    user_candidate = session.user_id or user_id or org_id or tenant_candidate
    tenant_value = str(tenant_candidate) if tenant_candidate else None
    user_value = str(user_candidate) if user_candidate else None
    if tenant_value and not user_value:
        user_value = tenant_value
    if user_value and not tenant_value:
        tenant_value = user_value
    return tenant_value, user_value


logger = get_logger(__name__)

_GRID_CELL_LIMIT = 25
_QUOTA_PROBLEM_TYPE = "https://kofinance.ai/docs/errors/plan-quota"
_CHAT_ACTION_LABEL = "AI 분석"


def _plan_label(plan: PlanContext) -> str:
    tier_value = getattr(plan.tier, "value", str(plan.tier))
    normalized = str(tier_value or "").replace("_", " ").strip()
    return normalized.title() or "Plan"


def _enforce_chat_quota(plan: PlanContext, user_id: Optional[uuid.UUID]) -> None:
    if not user_id:
        return
    decision = evaluate_quota("rag.chat", user_id=user_id, org_id=None, context="rag-service")
    if decision is None or decision.allowed or decision.backend_error:
        return
    plan_label = _plan_label(plan)
    limit = decision.limit or 0
    if limit == 0:
        status_code = status.HTTP_403_FORBIDDEN
        code = "plan.chat_quota_unavailable"
        message = f"{plan_label} 플랜에서는 {_CHAT_ACTION_LABEL}을(를) 사용할 수 없습니다."
    else:
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        code = "plan.chat_quota_exceeded"
        message = f"{plan_label} 플랜 {_CHAT_ACTION_LABEL} 한도를 모두 사용했습니다."
    detail = {
        "type": _QUOTA_PROBLEM_TYPE,
        "title": message,
        "detail": message,
        "code": code,
        "planTier": getattr(plan.tier, "value", str(plan.tier)),
        "quota": {
            "action": "rag.chat",
            "remaining": decision.remaining,
            "limit": decision.limit,
            "cost": 1,
        },
    }
    raise HTTPException(status_code=status_code, detail=detail)

NO_CONTEXT_ANSWER = "관련 증거를 찾지 못했습니다. 다른 키워드나 기간으로 다시 질문해 주세요."
INTENT_GENERAL_MESSAGE = "요청하신 내용은 정책상 바로 제공되지 않습니다. 보다 구체적인 배경이나 합법적 목적을 함께 알려 주세요."
INTENT_BLOCK_MESSAGE = SAFE_MESSAGE
INTENT_WARNING_CODE = "intent_filter"


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID header.") from exc


def _default_lightmem_user_id() -> Optional[uuid.UUID]:
    return lightmem_gate.default_user_id()


def _resolve_lightmem_user_id(value: Optional[str]) -> Optional[uuid.UUID]:
    if value:
        return _parse_uuid(value)
    return _default_lightmem_user_id()


def _load_user_lightmem_settings(
    user_id: Optional[uuid.UUID],
) -> Optional[UserLightMemSettings]:
    return lightmem_gate.load_user_settings(user_id)


def resolve_rag_deeplink(token: str) -> RAGDeeplinkPayload:
    """Resolve a signed deeplink token and expose the underlying citation metadata."""

    try:
        payload = deeplink_service.resolve_token(token)
    except deeplink_service.DeeplinkDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except deeplink_service.DeeplinkExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except deeplink_service.DeeplinkError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return RAGDeeplinkPayload.model_validate(payload)


def record_rag_telemetry(
    telemetry: RAGTelemetryRequest,
    request: Request,
    x_user_id: Optional[str],
    x_org_id: Optional[str],
    plan: PlanContext,
) -> RAGTelemetryResponse:
    """Capture client-side telemetry for deeplink/viewer UX."""

    user_id = _resolve_lightmem_user_id(x_user_id)
    org_id = _parse_uuid(x_org_id)
    accepted = 0
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    for event in telemetry.events:
        if event.name not in _ALLOWED_TELEMETRY_EVENTS:
            continue
        normalized_source = rag_audit.telemetry_source(event)
        reason = rag_audit.telemetry_reason(event.name, event.payload, _FAILURE_EVENTS)
        rag_metrics.record_event(event.name, source=normalized_source, reason=reason)

        event_timestamp = (event.timestamp or datetime.now(timezone.utc)).isoformat()
        extra_payload = rag_audit.telemetry_extra_payload(event.payload)
        extra_payload.update(
            {
                "source": normalized_source,
                "event": event.name,
                "timestamp": event_timestamp,
            }
        )
        if reason:
            extra_payload.setdefault("reason", reason)
        if client_ip:
            extra_payload["client_ip"] = client_ip
        if user_agent:
            extra_payload["user_agent"] = user_agent

        target_id = (
            extra_payload.get("chunk_id")
            or extra_payload.get("document_id")
            or event.payload.get("session_id")
            or event.payload.get("sessionId")
        )
        try:
            audit_rag_event(
                action=f"rag.telemetry.{event.name}",
                user_id=user_id,
                org_id=org_id,
                target_id=str(target_id) if target_id else None,
                feature_flags=plan.feature_flags(),
                extra=extra_payload,
            )
        except Exception:  # pragma: no cover - audit best-effort
            logger.debug("Failed to persist telemetry audit event for %s", event.name, exc_info=True)
        accepted += 1

    if accepted == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid telemetry events supplied.")
    return RAGTelemetryResponse(accepted=accepted)


def _enqueue_session_summary_if_allowed(plan_memory_enabled: bool, needs_summary: bool, session_id: uuid.UUID) -> None:
    if plan_memory_enabled and needs_summary:
        chat_service.enqueue_session_summary(session_id)


def _validate_grid_request(
    payload: RagGridRequest,
) -> None:
    cell_count = len(payload.tickers) * len(payload.questions)
    if cell_count > _GRID_CELL_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "rag.grid_too_large",
                "message": f"요청 가능한 셀 수가 {_GRID_CELL_LIMIT}개 제한을 초과했습니다.",
            },
        )


@dataclass(slots=True)
class IntentGateResult:
    decision: str
    reason: Optional[str]
    model: Optional[str]
    response: Optional[RAGQueryResponse]
    route: RouteDecision


def _evaluate_intent_gate(
    ctx: "RagSessionStage",
    route_decision: RouteDecision,
    db: Session,
    *,
    plan_memory_enabled: bool,
) -> IntentGateResult:
    action = route_decision.action
    reason = route_decision.reason
    if action == RouteAction.BLOCK_COMPLIANCE:
        response, needs_summary = build_intent_reply(
            db,
            question=ctx.question,
            trace_id=ctx.trace_id,
            session=ctx.session,
            turn_id=ctx.turn_id,
            user_message=ctx.user_message,
            assistant_message=ctx.assistant_message,
            decision="block",
            reason=reason,
            model_used=None,
            conversation_memory=ctx.conversation_memory,
        )
        response.meta = {
            **(response.meta or {}),
            "memory": dict(ctx.memory_info),
            "router_action": action.value,
        }
        db.commit()
        _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, ctx.session.id)
        return IntentGateResult("block", reason, None, response, route_decision)
    if action == RouteAction.CLARIFY:
        response, needs_summary = build_intent_reply(
            db,
            question=ctx.question,
            trace_id=ctx.trace_id,
            session=ctx.session,
            turn_id=ctx.turn_id,
            user_message=ctx.user_message,
            assistant_message=ctx.assistant_message,
            decision="semi_pass",
            reason=reason,
            model_used=None,
            conversation_memory=ctx.conversation_memory,
        )
        response.meta = {
            **(response.meta or {}),
            "memory": dict(ctx.memory_info),
            "router_action": action.value,
        }
        db.commit()
        _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, ctx.session.id)
        return IntentGateResult("semi_pass", reason, None, response, route_decision)
    return IntentGateResult("pass", reason, None, None, route_decision)


def _resolve_route_decision(
    provided: Optional[RouteDecision],
    question: str,
) -> RouteDecision:
    if provided is not None:
        return provided
    try:
        return DEFAULT_ROUTER.route(question)
    except Exception as exc:
        logger.warning("SemanticRouter failed; falling back to RAG: %s", exc, exc_info=True)
        return RouteDecision(
            action=RouteAction.RAG_ANSWER,
            reason="router_error",
            confidence=0.0,
            metadata={"fallback": True, "error": str(exc)},
        )


def _handle_empty_vector_response(
    ctx: "RagSessionStage",
    retrieval_stage: "RagRetrievalStage",
    db: Session,
    *,
    plan_memory_enabled: bool,
) -> Optional[RAGQueryResponse]:
    if retrieval_stage.rag_mode != "vector" or retrieval_stage.context_chunks:
        return None
    response, needs_summary = build_empty_response(
        db,
        question=ctx.question,
        filing_id=retrieval_stage.selected_filing_id,
        trace_id=ctx.trace_id,
        session=ctx.session,
        turn_id=ctx.turn_id or uuid.uuid4(),
        user_message=ctx.user_message,
        assistant_message=ctx.assistant_message,
        conversation_memory=ctx.conversation_memory,
        related_filings=retrieval_stage.related_filings,
        judge_result=retrieval_stage.judge_result,
        rag_mode=retrieval_stage.rag_mode,
    )
    response.meta = {
        **(response.meta or {}),
        "memory": dict(ctx.memory_info),
    }
    db.commit()
    _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, ctx.session.id)
    return response


def _stringify_ms(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return None

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


def _build_related_filings(payload: Optional[Sequence[Mapping[str, Any]]]) -> List[RelatedFiling]:
    related: List[RelatedFiling] = []
    if not payload:
        return related
    for item in payload:
        filing_id = item.get("filing_id")
        if not filing_id:
            continue
        related.append(
            RelatedFiling(
                filing_id=str(filing_id),
                score=float(item.get("score") or 0.0),
                title=item.get("title"),
                sentiment=item.get("sentiment"),
                published_at=item.get("published_at"),
            )
        )
    return related


def _resolve_selected_filing_id(
    retrieval: Optional[vector_service.VectorSearchResult],
    requested_filing_id: Optional[str],
    related_filings: Sequence[RelatedFiling],
) -> Optional[str]:
    if retrieval and retrieval.filing_id:
        return retrieval.filing_id
    if requested_filing_id:
        return requested_filing_id
    if related_filings:
        return related_filings[0].filing_id
    return None


def _related_filings_meta(related_filings: Sequence[RelatedFiling]) -> List[Dict[str, Any]]:
    return [item.model_dump() for item in related_filings]


RELATIVE_LABEL_DISPLAY = {
    "today": "??",
    "yesterday": "??",
    "two_days_ago": "??",
    "this_week": "?? ?",
    "last_week": "?? ?",
    "this_month": "?? ?",
    "last_month": "?? ?",
}


def _apply_relative_date_filters(
    question: str,
    filters: Optional[Dict[str, Any]] = None,
    *,
    range_hint: Optional[date_range_parser.RelativeDateRange] = None,
) -> Tuple[Dict[str, Any], Optional[date_range_parser.RelativeDateRange]]:
    updated_filters = dict(filters or {})
    relative_range = range_hint or date_range_parser.parse_relative_date_range(question)
    if not relative_range:
        return updated_filters, None

    min_ts = relative_range.start.timestamp()
    max_ts = relative_range.end.timestamp()

    existing_min = safe_float(updated_filters.get("min_published_at_ts"))
    existing_max = safe_float(updated_filters.get("max_published_at_ts"))

    if existing_min is None or (min_ts is not None and min_ts > existing_min):
        updated_filters["min_published_at_ts"] = min_ts
    if existing_max is None or (max_ts is not None and max_ts < existing_max):
        updated_filters["max_published_at_ts"] = max_ts

    return updated_filters, relative_range


def _build_prompt_metadata(
    relative_range: Optional[date_range_parser.RelativeDateRange],
) -> Dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(date_range_parser.KST)
    metadata: Dict[str, Any] = {
        "current_datetime_utc": now_utc.isoformat(),
        "current_datetime_local": now_local.isoformat(),
        "current_date_local": now_local.strftime("%Y-%m-%d"),
    }

    if relative_range:
        start_local = relative_range.start.astimezone(date_range_parser.KST)
        end_local = relative_range.end.astimezone(date_range_parser.KST)
        label_display = RELATIVE_LABEL_DISPLAY.get(relative_range.label, relative_range.label)
        metadata["relative_date_range"] = {
            "label": relative_range.label,
            "label_display": label_display,
            "start_utc": relative_range.start.isoformat(),
            "end_utc": relative_range.end.isoformat(),
            "start_local": start_local.isoformat(),
            "end_local": end_local.isoformat(),
        }

    return metadata



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
    db: Optional[Session] = None,
) -> vector_service.VectorSearchResult:
    try:
        if db is not None and hybrid_search.is_hybrid_enabled():
            return hybrid_search.query_hybrid(
                db,
                question,
                filing_id=filing_id,
                top_k=top_k,
                max_filings=max_filings,
                filters=filters,
            )
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
    relative_range: Optional[date_range_parser.RelativeDateRange] = None,
    org_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
) -> RAGQueryResponse:
    judge_result = llm_service.assess_query_risk(question)
    judge_decision = (judge_result.get("decision") or "unknown") if judge_result else "unknown"
    rag_mode = (judge_result.get("rag_mode") or "vector") if judge_result else "vector"

    filters, relative_range = _apply_relative_date_filters(
        question,
        filters,
        range_hint=relative_range,
    )
    prompt_metadata = _build_prompt_metadata(relative_range)

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
        related_filings = _build_related_filings(retrieval.related_filings)
        selected_filing_id = _resolve_selected_filing_id(retrieval, filing_id, related_filings)

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
                    "related_filings": _related_filings_meta(related_filings),
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

    payload = llm_service.generate_rag_answer(
        question,
        context_chunks,
        judge_result=judge_result,
        prompt_metadata=prompt_metadata,
    )
    payload_rag_mode = payload.get("rag_mode") or rag_mode
    meta_payload = dict(payload.get("meta", {}))
    retrieval_meta = dict(meta_payload.get("retrieval") or {})
    retrieval_meta.setdefault("filing_id", selected_filing_id)
    retrieval_meta.setdefault("rag_mode", payload_rag_mode)
    meta_payload["retrieval"] = retrieval_meta
    meta_payload.setdefault("selected_filing_id", selected_filing_id)
    meta_payload.setdefault("related_filings", _related_filings_meta(related_filings))
    guard_meta = dict(meta_payload.get("guardrail") or {})
    guard_meta.setdefault("decision", payload.get("judge_decision"))
    guard_meta.setdefault("reason", payload.get("judge_reason"))
    guard_meta["rag_mode"] = payload_rag_mode
    meta_payload["guardrail"] = guard_meta
    if prompt_metadata:
        meta_payload.setdefault("prompt", prompt_metadata)

    evidence_context = _build_evidence_payload(payload.get("context") or context_chunks)
    snapshot_payload = deepcopy(evidence_context)
    evidence_context, diff_meta = rag_audit.attach_evidence_diff(evidence_context, trace_id=trace_id)
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
        rag_jobs.enqueue_self_check(
            {
                "question": question,
                "filing_id": selected_filing_id,
                "answer": response.model_dump(mode="json"),
                "context": context_chunks,
                "trace_id": trace_id,
            }
        )

    if snapshot_payload:
        rag_audit.enqueue_evidence_snapshot(
            snapshot_payload,
            author=None,
            trace_id=trace_id,
            org_id=org_id,
            user_id=user_id,
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

class RagSessionStage(BaseModel):
    question: str
    filing_id: Optional[str]
    filter_payload: Dict[str, Any]
    relative_range: Optional[date_range_parser.RelativeDateRange]
    prompt_metadata: Dict[str, Any]
    max_filings: Optional[int]
    trace_id: str
    user_id: Optional[uuid.UUID]
    org_id: Optional[uuid.UUID]
    turn_id: Optional[uuid.UUID]
    idempotency_key: Optional[str]
    user_meta: Dict[str, Any]
    plan_memory_enabled: bool
    session: ChatSession
    user_message: ChatMessage
    assistant_message: ChatMessage
    conversation_memory: Optional[Dict[str, Any]]
    memory_info: Dict[str, Any]
    memory_session_key: str
    tenant_id_value: Optional[str]
    user_id_value: Optional[str]

    class Config:
        arbitrary_types_allowed = True


class RagRetrievalStage(BaseModel):
    rag_mode: str
    judge_result: Optional[Dict[str, Any]]
    context_chunks: List[Dict[str, Any]]
    related_filings: List[RelatedFiling]
    selected_filing_id: Optional[str]
    retrieval: Optional[vector_service.VectorSearchResult]
    should_retrieve: bool

    class Config:
        arbitrary_types_allowed = True


class RagLLMStage(BaseModel):
    answer_text: str
    context: List[Dict[str, Any]]
    context_chunks: List[Dict[str, Any]]
    snapshot_payload: Optional[List[Dict[str, Any]]]
    diff_meta: Dict[str, Any]
    citations: Dict[str, List[Any]]
    warnings: List[str]
    highlights: List[Dict[str, Any]]
    error: Optional[Any]
    selected_filing_id: Optional[str]
    rag_mode: str
    latency_ms: int
    model_used: Optional[str]
    original_answer: Optional[str]
    judge_decision: Optional[str]
    judge_reason: Optional[str]
    retrieval_ids: List[Any]
    context_filters: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True


class RagAuditStage(BaseModel):
    trace_id: str
    turn_id: Optional[uuid.UUID]
    rag_mode: str
    intent_decision: str
    judge_decision: Optional[str]
    filing_id: Optional[str]
    error: Optional[Any]
    context_docs: int
    citation_stats: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True


def _prepare_rag_session(
    request: RAGQueryRequest,
    x_user_id: Optional[str],
    x_org_id: Optional[str],
    idempotency_key_header: Optional[str],
    plan: PlanContext,
    db: Session,
) -> RagSessionStage:
    question = request.question.strip()
    filing_id = request.filing_id.strip() if request.filing_id else None
    filter_payload = _prepare_vector_filters(request.filters)
    filter_payload, relative_range = _apply_relative_date_filters(question, filter_payload)
    prompt_metadata = _build_prompt_metadata(relative_range)
    max_filings = request.max_filings
    trace_id = str(uuid.uuid4())

    user_id = _resolve_lightmem_user_id(x_user_id)
    org_id = _parse_uuid(x_org_id)
    turn_id = _coerce_uuid(request.turn_id)
    idempotency_key = request.idempotency_key or idempotency_key_header

    _enforce_chat_quota(plan, user_id)

    user_meta = dict(request.meta or {})
    user_settings = _load_user_lightmem_settings(user_id)
    plan_memory_enabled = _plan_memory_enabled(plan, user_settings=user_settings)

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
    memory_session_key = f"chat:{session.id}"
    tenant_id_value, user_id_value = _memory_subject_ids(session, user_id, org_id)
    conversation_memory, memory_info = rag_audit.merge_lightmem_context(
        question,
        conversation_memory,
        session_key=memory_session_key,
        tenant_id=tenant_id_value,
        user_id=user_id_value,
        plan_memory_enabled=plan_memory_enabled,
    )

    return RagSessionStage(
        question=question,
        filing_id=filing_id,
        filter_payload=filter_payload,
        relative_range=relative_range,
        prompt_metadata=prompt_metadata,
        max_filings=max_filings,
        trace_id=trace_id,
        user_id=user_id,
        org_id=org_id,
        turn_id=turn_id,
        idempotency_key=idempotency_key,
        user_meta=user_meta,
        plan_memory_enabled=plan_memory_enabled,
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        conversation_memory=conversation_memory,
        memory_info=memory_info,
        memory_session_key=memory_session_key,
        tenant_id_value=tenant_id_value,
        user_id_value=user_id_value,
    )


def _run_retrieval_stage(
    ctx: RagSessionStage,
    request: RAGQueryRequest,
    db: Session,
) -> RagRetrievalStage:
    judge_result = llm_service.assess_query_risk(ctx.question)
    rag_mode = (judge_result.get("rag_mode") or "vector") if judge_result else "vector"
    judge_decision = (judge_result.get("decision") or "unknown") if judge_result else "unknown"
    should_retrieve = rag_mode != "none" and judge_decision in {"pass", "unknown"}

    context_chunks: List[Dict[str, Any]] = []
    related_filings: List[RelatedFiling] = []
    selected_filing_id = ctx.filing_id
    retrieval: Optional[vector_service.VectorSearchResult] = None

    if should_retrieve:
        retrieval = _vector_search(
            ctx.question,
            filing_id=ctx.filing_id,
            top_k=request.top_k,
            max_filings=ctx.max_filings,
            filters=ctx.filter_payload,
            db=db,
        )
        context_chunks = retrieval.chunks
        related_filings = _build_related_filings(retrieval.related_filings)
        selected_filing_id = _resolve_selected_filing_id(retrieval, ctx.filing_id, related_filings)

    return RagRetrievalStage(
        rag_mode=rag_mode,
        judge_result=judge_result,
        context_chunks=context_chunks,
        related_filings=related_filings,
        selected_filing_id=selected_filing_id,
        retrieval=retrieval,
        should_retrieve=should_retrieve,
    )


def _run_llm_stage(
    ctx: RagSessionStage,
    retrieval: RagRetrievalStage,
    *,
    prompt_metadata: Dict[str, Any],
    filter_payload: Dict[str, Any],
    db: Session,
) -> RagLLMStage:
    started_at = datetime.now(timezone.utc)
    result = llm_service.generate_rag_answer(
        ctx.question,
        retrieval.context_chunks,
        conversation_memory=ctx.conversation_memory,
        judge_result=retrieval.judge_result,
        prompt_metadata=prompt_metadata,
    )
    rag_mode = result.get("rag_mode") or retrieval.rag_mode
    latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)

    context = _build_evidence_payload(result.get("context") or retrieval.context_chunks)
    snapshot_payload = deepcopy(context)
    context, diff_meta = rag_audit.attach_evidence_diff(context, db=db, trace_id=ctx.trace_id)

    return RagLLMStage(
        answer_text=result.get("answer", "답변을 준비하지 못했습니다."),
        context=context,
        context_chunks=retrieval.context_chunks,
        snapshot_payload=snapshot_payload,
        diff_meta=diff_meta,
        citations=dict(result.get("citations") or {}),
        warnings=list(result.get("warnings") or []),
        highlights=list(result.get("highlights") or []),
        error=result.get("error"),
        selected_filing_id=retrieval.selected_filing_id,
        rag_mode=rag_mode,
        latency_ms=latency_ms,
        model_used=result.get("model_used"),
        original_answer=result.get("original_answer"),
        judge_decision=result.get("judge_decision"),
        judge_reason=result.get("judge_reason"),
        retrieval_ids=[
            chunk.get("id") for chunk in retrieval.context_chunks if isinstance(chunk.get("id"), str) and chunk.get("id")
        ],
        context_filters=filter_payload,
    )


def _render_rag_response(
    db: Session,
    ctx: RagSessionStage,
    retrieval: RagRetrievalStage,
    llm_stage: RagLLMStage,
    *,
    intent_decision: str,
    intent_reason: Optional[str],
    intent_model: Optional[str],
    router_action: str,
    persist_context: bool = True,
) -> Tuple[RAGQueryResponse, bool]:
    conversation_summary = None
    recent_turn_count = 0
    if ctx.conversation_memory:
        conversation_summary = ctx.conversation_memory.get("summary")
        recent_turn_count = len(ctx.conversation_memory.get("recent_turns") or [])

    meta_payload = {
        "model": llm_stage.model_used,
        "prompt_version": ctx.user_meta.get("prompt_version"),
        "latency_ms": llm_stage.latency_ms,
        "input_tokens": ctx.user_meta.get("input_tokens"),
        "output_tokens": ctx.user_meta.get("output_tokens"),
        "cost": ctx.user_meta.get("cost"),
        "retrieval": {
            "doc_ids": llm_stage.retrieval_ids,
            "hit_at_k": len(llm_stage.context_chunks),
            "filing_id": llm_stage.selected_filing_id,
            "filters": llm_stage.context_filters,
            "rag_mode": llm_stage.rag_mode,
        },
        "guardrail": {
            "decision": llm_stage.judge_decision,
            "reason": llm_stage.judge_reason,
            "rag_mode": llm_stage.rag_mode,
        },
        "turnId": str(ctx.turn_id) if ctx.turn_id else None,
        "traceId": ctx.trace_id,
        "citations": llm_stage.citations,
        "conversation_summary": conversation_summary,
        "recent_turn_count": recent_turn_count,
        "answer_preview": chat_service.trim_preview(llm_stage.answer_text),
        "selected_filing_id": llm_stage.selected_filing_id,
        "related_filings": _related_filings_meta(retrieval.related_filings),
        "intent_decision": intent_decision,
        "intent_reason": intent_reason,
        "intent_model": intent_model,
        "router_action": router_action,
    }
    if ctx.prompt_metadata:
        meta_payload["prompt"] = ctx.prompt_metadata
    meta_payload["evidence_version"] = "v2"
    meta_payload["evidence_diff"] = llm_stage.diff_meta

    summary_captured = rag_audit.store_lightmem_summary(
        question=ctx.question,
        answer=llm_stage.answer_text,
        session=ctx.session,
        turn_id=ctx.turn_id,
        session_key=ctx.memory_session_key,
        tenant_id=ctx.tenant_id_value,
        user_id=ctx.user_id_value,
        plan_memory_enabled=ctx.plan_memory_enabled,
        rag_mode=llm_stage.rag_mode,
        filing_id=llm_stage.selected_filing_id,
    )
    if summary_captured:
        ctx.memory_info["captured"] = True
    meta_payload["memory"] = dict(ctx.memory_info)

    update_payload = {
        "db": db,
        "message_id": ctx.assistant_message.id,
        "state": "error" if llm_stage.error else "ready",
        "error_code": llm_stage.error if llm_stage.error else None,
        "error_message": llm_stage.error if llm_stage.error else None,
        "content": llm_stage.answer_text,
        "meta": meta_payload,
    }
    if persist_context:
        update_payload["context"] = llm_stage.context
    chat_service.update_message_state(**update_payload)
    needs_summary = chat_service.should_trigger_summary(db, ctx.session)

    snapshot_author: Optional[str] = None
    if ctx.user_id:
        snapshot_author = str(ctx.user_id)
    elif ctx.session.user_id:
        snapshot_author = str(ctx.session.user_id)
    if llm_stage.snapshot_payload:
        rag_audit.enqueue_evidence_snapshot(
            llm_stage.snapshot_payload,
            author=snapshot_author,
            trace_id=ctx.trace_id,
            org_id=ctx.org_id or ctx.session.org_id,
            user_id=ctx.user_id or ctx.session.user_id,
        )

    response = RAGQueryResponse(
        question=ctx.question,
        filing_id=llm_stage.selected_filing_id,
        session_id=ctx.session.id,
        turn_id=ctx.turn_id,
        user_message_id=ctx.user_message.id,
        assistant_message_id=ctx.assistant_message.id,
        answer=llm_stage.answer_text,
        context=llm_stage.context,
        citations=llm_stage.citations,
        warnings=llm_stage.warnings,
        highlights=llm_stage.highlights,
        error=llm_stage.error,
        original_answer=llm_stage.original_answer,
        model_used=llm_stage.model_used,
        trace_id=ctx.trace_id,
        judge_decision=llm_stage.judge_decision,
        judge_reason=llm_stage.judge_reason,
        meta=meta_payload,
        state="error" if llm_stage.error else "ready",
        related_filings=retrieval.related_filings,
        rag_mode=llm_stage.rag_mode,
    )
    return response, needs_summary


def _record_rag_audit(
    ctx: RagSessionStage,
    plan: PlanContext,
    *,
    retrieval: RagRetrievalStage,
    llm_stage: RagLLMStage,
    intent_decision: str,
    response: RAGQueryResponse,
) -> RagAuditStage:
    citation_stats = rag_audit.build_citation_stats(llm_stage.citations)
    audit_stage = RagAuditStage(
        trace_id=ctx.trace_id,
        turn_id=ctx.turn_id,
        rag_mode=llm_stage.rag_mode,
        intent_decision=intent_decision,
        judge_decision=llm_stage.judge_decision,
        filing_id=response.filing_id,
        error=llm_stage.error,
        context_docs=len(response.context),
        citation_stats=citation_stats,
    )
    audit_rag_event(
        action="rag.query",
        user_id=ctx.user_id,
        org_id=ctx.org_id,
        target_id=str(ctx.session.id),
        feature_flags=plan.feature_flags(),
        extra={
            "trace_id": ctx.trace_id,
            "turn_id": str(ctx.turn_id) if ctx.turn_id else None,
            "rag_mode": llm_stage.rag_mode,
            "intent_decision": intent_decision,
            "judge_decision": llm_stage.judge_decision,
            "filing_id": response.filing_id,
            "error": llm_stage.error,
            "context_docs": len(response.context),
            "citation_stats": citation_stats,
        },
    )
    return audit_stage


def query_rag(
    request: RAGQueryRequest,
    x_user_id: Optional[str],
    x_org_id: Optional[str],
    idempotency_key_header: Optional[str],
    plan: PlanContext,
    db: Session,
    route_decision: Optional[RouteDecision] = None,
) -> RAGQueryResponse:
    ctx = _prepare_rag_session(
        request,
        x_user_id,
        x_org_id,
        idempotency_key_header,
        plan,
        db,
    )
    question = ctx.question
    filing_id = ctx.filing_id
    filter_payload = ctx.filter_payload
    relative_range = ctx.relative_range
    prompt_metadata = ctx.prompt_metadata
    max_filings = ctx.max_filings
    trace_id = ctx.trace_id
    user_id = ctx.user_id
    org_id = ctx.org_id
    turn_id = ctx.turn_id
    plan_memory_enabled = ctx.plan_memory_enabled
    session = ctx.session
    user_message = ctx.user_message
    assistant_message = ctx.assistant_message
    conversation_memory = ctx.conversation_memory
    memory_session_key = ctx.memory_session_key
    tenant_id_value = ctx.tenant_id_value
    user_id_value = ctx.user_id_value
    memory_info = ctx.memory_info
    user_meta = ctx.user_meta

    try:
        route_decision = _resolve_route_decision(route_decision, question)
        ctx.user_meta["router_action"] = route_decision.action.value
        ctx.user_meta["router_confidence"] = route_decision.confidence

        intent_gate = _evaluate_intent_gate(
            ctx,
            route_decision,
            db,
            plan_memory_enabled=plan_memory_enabled,
        )
        if intent_gate.response:
            return intent_gate.response

        retrieval_stage = _run_retrieval_stage(ctx, request, db)
        empty_response = _handle_empty_vector_response(
            ctx,
            retrieval_stage,
            db,
            plan_memory_enabled=plan_memory_enabled,
        )
        if empty_response:
            return empty_response

        llm_stage = _run_llm_stage(
            ctx,
            retrieval_stage,
            prompt_metadata=ctx.prompt_metadata,
            filter_payload=ctx.filter_payload,
            db=db,
        )
        if llm_stage.error and not (
            str(llm_stage.error or "").startswith("missing_citations")
            or str(llm_stage.error or "").startswith("guardrail_violation")
        ):
            chat_service.update_message_state(
                db,
                message_id=ctx.assistant_message.id,
                state="error",
                error_code="llm_error",
                error_message=str(llm_stage.error),
                meta={"latency_ms": llm_stage.latency_ms},
            )
            db.commit()
            raise HTTPException(status_code=500, detail=f"LLM answer failed: {llm_stage.error}")

        response, needs_summary = _render_rag_response(
            db,
            ctx,
            retrieval_stage,
            llm_stage,
            intent_decision=intent_gate.decision,
            intent_reason=intent_gate.reason,
            intent_model=intent_gate.model,
            router_action=intent_gate.route.action.value,
        )
        _record_rag_audit(
            ctx,
            plan,
            retrieval=retrieval_stage,
            llm_stage=llm_stage,
            intent_decision=intent_gate.decision,
            response=response,
        )

        if request.run_self_check:
            payload = {
                "question": ctx.question,
                "filing_id": llm_stage.selected_filing_id,
                "answer": response.model_dump(mode="json"),
                "context": llm_stage.context_chunks,
                "trace_id": ctx.trace_id,
            }
            rag_jobs.enqueue_self_check(payload)

        db.commit()
        _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, ctx.session.id)
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
            relative_range=relative_range,
            org_id=org_id,
            user_id=user_id,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def query_rag_stream(
    request: RAGQueryRequest,
    x_user_id: Optional[str],
    x_org_id: Optional[str],
    idempotency_key_header: Optional[str],
    plan: PlanContext,
    db: Session,
    route_decision: Optional[RouteDecision] = None,
):
    ctx = _prepare_rag_session(
        request,
        x_user_id,
        x_org_id,
        idempotency_key_header,
        plan,
        db,
    )
    question = ctx.question
    filing_id = ctx.filing_id
    filter_payload = ctx.filter_payload
    relative_range = ctx.relative_range
    prompt_metadata = ctx.prompt_metadata
    max_filings = ctx.max_filings
    trace_id = ctx.trace_id
    user_id = ctx.user_id
    org_id = ctx.org_id
    turn_id = ctx.turn_id
    plan_memory_enabled = ctx.plan_memory_enabled
    session = ctx.session
    user_message = ctx.user_message
    assistant_message = ctx.assistant_message
    conversation_memory = ctx.conversation_memory
    memory_session_key = ctx.memory_session_key
    tenant_id_value = ctx.tenant_id_value
    user_id_value = ctx.user_id_value
    memory_info = ctx.memory_info
    user_meta = ctx.user_meta

    try:
        route_decision = _resolve_route_decision(route_decision, question)
        ctx.user_meta["router_action"] = route_decision.action.value
        ctx.user_meta["router_confidence"] = route_decision.confidence
        intent_gate = _evaluate_intent_gate(
            ctx,
            route_decision,
            db,
            plan_memory_enabled=plan_memory_enabled,
        )
        intent_decision = intent_gate.decision
        intent_reason = intent_gate.reason
        intent_model = intent_gate.model

        if intent_gate.response:
            payload_json = intent_gate.response.model_dump(mode="json")

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
        rag_mode = (judge_result.get("rag_mode") or "vector") if judge_result else "vector"

        filters_v2 = RagQueryFiltersSchema(
            dateGte=request.filters.min_published_at,
            dateLte=request.filters.max_published_at,
            tickers=[request.filters.ticker] if request.filters.ticker else [],
            sectors=[request.filters.sector] if request.filters.sector else [],
        )
        pipeline_request = RagQueryV2Request(
            query=question,
            filingId=filing_id,
            tickers=list(filters_v2.tickers),
            topK=request.top_k or 6,
            maxFilings=max_filings,
            filters=filters_v2,
        )
        pipeline_result = rag_pipeline.run_rag_query(db, pipeline_request)
        context_chunks = pipeline_result.raw_chunks
        related_filings = _build_related_filings(pipeline_result.related_documents)
        active_filing_id = pipeline_result.trace.get("selectedFilingId") or filing_id

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
            _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, session.id)

            payload = response.model_dump(mode="json")
            payload["evidence"] = []
            payload["warnings"] = [warning.message for warning in pipeline_result.warnings]

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
        related_meta = _related_filings_meta(related_filings)

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
            if prompt_metadata:
                initial_meta["prompt"] = prompt_metadata
            initial_meta["memory"] = dict(memory_info)
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
                    conversation_memory=conversation_memory,
                    judge_result=judge_result,
                    prompt_metadata=prompt_metadata,
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

                answer_text = final_payload.get("answer") or "".join(streamed_tokens) or SAFE_MESSAGE
                context = _build_evidence_payload(final_payload.get("context") or context_chunks)
                snapshot_payload = deepcopy(context)
                context, diff_meta = rag_audit.attach_evidence_diff(context, db=db, trace_id=trace_id)
                citations: Dict[str, List[Any]] = dict(final_payload.get("citations") or {})
                llm_warning_messages = [
                    warning
                    for warning in list(final_payload.get("warnings") or [])
                    if isinstance(warning, str) and warning.strip()
                ]
                highlights: List[Dict[str, object]] = list(final_payload.get("highlights") or [])
                error = final_payload.get("error")

                latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
                retrieval_ids = [chunk.get("id") for chunk in context_chunks if isinstance(chunk.get("id"), str)]
                evidence_payload = [
                    item.model_dump(mode="json", exclude_none=True) for item in pipeline_result.evidence
                ]
                pipeline_warning_messages = [warning.message for warning in pipeline_result.warnings]
                combined_warnings = pipeline_warning_messages + llm_warning_messages
                state_value = str(final_payload.get("state") or "ready")

                streaming_retrieval = RagRetrievalStage(
                    rag_mode=payload_rag_mode,
                    judge_result=judge_result,
                    context_chunks=context_chunks,
                    related_filings=related_filings,
                    selected_filing_id=selected_filing_id,
                    retrieval=None,
                    should_retrieve=True,
                )
                streaming_llm = RagLLMStage(
                    answer_text=answer_text,
                    context=context,
                    context_chunks=context_chunks,
                    snapshot_payload=snapshot_payload,
                    diff_meta=diff_meta,
                    citations=citations,
                    warnings=combined_warnings,
                    highlights=highlights,
                    error=error,
                    selected_filing_id=selected_filing_id,
                    rag_mode=payload_rag_mode,
                    latency_ms=latency_ms,
                    model_used=final_payload.get("model_used"),
                    original_answer=final_payload.get("original_answer"),
                    judge_decision=final_payload.get("judge_decision"),
                    judge_reason=final_payload.get("judge_reason"),
                    retrieval_ids=[rid for rid in retrieval_ids if rid],
                    context_filters=filter_payload,
                )
                response, needs_summary = _render_rag_response(
                    db,
                    ctx,
                    streaming_retrieval,
                    streaming_llm,
                    intent_decision=intent_decision,
                    intent_reason=intent_reason,
                    intent_model=intent_model,
                    router_action=route_decision.action.value,
                )
                _record_rag_audit(
                    ctx,
                    plan,
                    retrieval=streaming_retrieval,
                    llm_stage=streaming_llm,
                    intent_decision=intent_decision,
                    response=response,
                )

                payload_json = response.model_dump(mode="json")
                payload_json["evidence"] = evidence_payload
                payload_json["warnings"] = warnings
                payload_json["sessionId"] = str(session.id)
                payload_json["turnId"] = str(turn_id)
                payload_json["userMessageId"] = str(user_message.id)
                payload_json["assistantMessageId"] = str(assistant_message.id)
                payload_json["traceId"] = trace_id
                payload_json["ragMode"] = payload_rag_mode
                payload_json["state"] = state_value
                payload_json["warnings"] = combined_warnings

                if request.run_self_check:
                    rag_jobs.enqueue_self_check(
                        {
                            "question": question,
                            "filing_id": selected_filing_id,
                            "answer": response.model_dump(mode="json"),
                            "context": context_chunks,
                            "trace_id": trace_id,
                        }
                    )

                db.commit()
                _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, session.id)

                yield json.dumps(
                    {
                        "event": "done",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "payload": payload_json,
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


def query_rag_v2(
    payload: RagQueryV2Request,
    x_user_id: Optional[str],
    x_org_id: Optional[str],
    plan: PlanContext,
    db: Session,
    route_decision: Optional[RouteDecision] = None,
) -> RagQueryV2Response:
    question = payload.query.strip()
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question_required")

    route_decision = _resolve_route_decision(route_decision, question)
    trace_id = str(uuid.uuid4())
    user_id = _resolve_lightmem_user_id(x_user_id)
    org_id = _parse_uuid(x_org_id)
    plan_memory_enabled = plan.memory_chat_enabled
    turn_id = _coerce_uuid(payload.turnId)
    user_message_id = _parse_uuid(payload.userMessageId)
    assistant_message_id = _parse_uuid(payload.assistantMessageId)
    retry_of_message_id = _parse_uuid(payload.retryOfMessageId)
    session_uuid = _parse_uuid(payload.sessionId)

    _enforce_chat_quota(plan, user_id)

    user_meta = dict(payload.meta or {})
    user_meta.setdefault("router_action", route_decision.action.value)
    user_meta.setdefault("router_confidence", route_decision.confidence)
    user_settings = _load_user_lightmem_settings(user_id)
    plan_memory_enabled = _plan_memory_enabled(plan, user_settings=user_settings)

    try:
        session = _resolve_session(
            db,
            session_id=session_uuid,
            user_id=user_id,
            org_id=org_id,
            filing_id=payload.filingId,
        )
        user_message = _ensure_user_message(
            db,
            session=session,
            user_message_id=user_message_id,
            question=question,
            turn_id=turn_id,
            idempotency_key=payload.idempotencyKey,
            meta=user_meta,
        )
        assistant_message = _ensure_assistant_message(
            db,
            session=session,
            assistant_message_id=assistant_message_id,
            turn_id=turn_id,
            idempotency_key=None,
            retry_of_message_id=retry_of_message_id,
            initial_state="pending",
        )

        conversation_memory = chat_service.build_conversation_memory(db, session)
        memory_session_key = f"chat:{session.id}"
        tenant_id_value, user_id_value = _memory_subject_ids(session, user_id, org_id)
        conversation_memory, memory_info = rag_audit.merge_lightmem_context(
            question,
            conversation_memory,
            session_key=memory_session_key,
            tenant_id=tenant_id_value,
            user_id=user_id_value,
            plan_memory_enabled=plan_memory_enabled,
        )

        judge_result = llm_service.assess_query_risk(question)
        rag_mode_hint = judge_result.get("rag_mode") if judge_result else None

        filters_for_prompt: Dict[str, Any] = {}
        primary_ticker = next((ticker for ticker in (payload.filters.tickers or payload.tickers) if ticker), None)
        if primary_ticker:
            filters_for_prompt["ticker"] = primary_ticker
        if payload.filters.dateGte:
            try:
                filters_for_prompt["min_published_at_ts"] = datetime.fromisoformat(
                    payload.filters.dateGte.replace("Z", "+00:00")
                ).timestamp()
            except ValueError:
                pass
        if payload.filters.dateLte:
            try:
                filters_for_prompt["max_published_at_ts"] = datetime.fromisoformat(
                    payload.filters.dateLte.replace("Z", "+00:00")
                ).timestamp()
            except ValueError:
                pass

        filters_for_prompt, relative_range = _apply_relative_date_filters(
            question,
            filters_for_prompt,
        )
        prompt_metadata = _build_prompt_metadata(relative_range)

        try:
            pipeline_result = rag_pipeline.run_rag_query(db, payload)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "rag.pipeline_unavailable", "message": "RAG 파이프라인을 잠시 사용할 수 없습니다. 잠시 후 다시 시도해 주세요."},
            ) from exc

        llm_payload = llm_service.generate_rag_answer(
            question,
            pipeline_result.raw_chunks,
            judge_result=judge_result,
            prompt_metadata=prompt_metadata,
        )
        payload_rag_mode = llm_payload.get("rag_mode") or rag_mode_hint or "vector"

        context_chunks = pipeline_result.raw_chunks
        legacy_context = _build_evidence_payload(context_chunks)
        snapshot_payload = deepcopy(legacy_context)
        legacy_context, diff_meta = rag_audit.attach_evidence_diff(legacy_context, db=db, trace_id=trace_id)

        warning_messages: List[str] = []
        response_warnings: List[RagWarningSchema] = []
        for warning in pipeline_result.warnings:
            warning_messages.append(warning.message)
            response_warnings.append(warning)
        for warning_text in llm_payload.get("warnings") or []:
            if isinstance(warning_text, str) and warning_text.strip():
                warning_messages.append(warning_text.strip())
                response_warnings.append(RagWarningSchema(code="llm.warning", message=warning_text.strip()))

        related_filings = _build_related_filings(pipeline_result.related_documents)
        selected_filing_id = pipeline_result.trace.get("selectedFilingId")

        meta_payload = dict(llm_payload.get("meta", {}))
        retrieval_meta = dict(meta_payload.get("retrieval") or {})
        retrieval_meta.setdefault("filing_id", selected_filing_id)
        retrieval_meta.setdefault("doc_ids", [doc.get("filing_id") for doc in pipeline_result.related_documents])
        retrieval_meta["rag_mode"] = payload_rag_mode
        meta_payload["retrieval"] = retrieval_meta
        meta_payload.setdefault("selected_filing_id", selected_filing_id)
        meta_payload.setdefault("related_filings", _related_filings_meta(related_filings))

        guard_meta = dict(meta_payload.get("guardrail") or {})
        guard_meta.setdefault("decision", llm_payload.get("judge_decision"))
        guard_meta.setdefault("reason", llm_payload.get("judge_reason"))
        guard_meta["rag_mode"] = payload_rag_mode
        meta_payload["guardrail"] = guard_meta
        if prompt_metadata:
            meta_payload.setdefault("prompt", prompt_metadata)
        meta_payload["evidence_version"] = "v2"
        meta_payload["evidence_diff"] = diff_meta

        citation_stats = rag_audit.build_citation_stats(llm_payload.get("citations") or {})
        meta_payload.setdefault("citation_stats", citation_stats)

        answer_text = llm_payload.get("answer") or ""
        state_value = llm_payload.get("state", "ready")

        chat_service.update_message_state(
            db,
            message_id=assistant_message.id,
            state=state_value,
            error_code=llm_payload.get("error"),
            error_message=llm_payload.get("error"),
            content=answer_text,
            context=legacy_context,
            meta=meta_payload,
        )
        needs_summary = chat_service.should_trigger_summary(db, session)

        if payload.runSelfCheck:
            rag_jobs.enqueue_self_check(
                {
                    "question": question,
                    "filing_id": selected_filing_id,
                    "answer": {
                        "answer": answer_text,
                        "citations": llm_payload.get("citations"),
                        "warnings": warning_messages,
                    },
                    "context": context_chunks,
                    "trace_id": trace_id,
                }
            )

        if snapshot_payload:
            rag_audit.enqueue_evidence_snapshot(
                snapshot_payload,
                author=str(user_id or session.user_id or "system"),
                trace_id=trace_id,
                org_id=org_id or session.org_id,
                user_id=user_id or session.user_id,
            )

        db.commit()
        _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, session.id)

        evidence_payload = [item.model_dump(mode="json", exclude_none=True) for item in pipeline_result.evidence]
        citations_payload: Dict[str, List[Any]] = {}
        citations_raw = llm_payload.get("citations")
        if isinstance(citations_raw, dict):
            for key, value in citations_raw.items():
                if isinstance(key, str) and isinstance(value, list):
                    citations_payload[key] = value
        meta_response = {
            "traceId": trace_id,
            "retrievalMs": _stringify_ms(pipeline_result.timings_ms.get("retrievalMs")),
            "totalMs": _stringify_ms(pipeline_result.timings_ms.get("totalMs")),
            "relatedCount": str(len(pipeline_result.related_documents)),
            "modelUsed": llm_payload.get("model_used"),
        }

        return RagQueryV2Response(
            answer=answer_text,
            evidence=evidence_payload,
            warnings=response_warnings,
            citations=citations_payload,
            sessionId=str(session.id),
            turnId=str(turn_id),
            userMessageId=str(user_message.id),
            assistantMessageId=str(assistant_message.id),
            traceId=trace_id,
            state=state_value,
            ragMode=payload_rag_mode,
            meta=meta_response,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def query_rag_grid(
    payload: RagGridRequest,
    x_user_id: Optional[str],
    x_org_id: Optional[str],
    plan: PlanContext,
    db: Session,
) -> RagGridResponse:
    _validate_grid_request(payload)

    try:
        return rag_grid.run_grid(db, payload)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "rag.grid_unavailable", "message": "Grid 실행을 잠시 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."},
        ) from exc


def create_rag_grid_job(
    payload: RagGridRequest,
    x_user_id: Optional[str],
    x_org_id: Optional[str],
    plan: PlanContext,
    db: Session,
) -> RagGridJobResponse:
    _validate_grid_request(payload)

    try:
        job = rag_grid.create_grid_job(db, payload, requested_by=_parse_uuid(x_user_id))
        rag_grid.enqueue_grid_job(job.id)
        return rag_grid.serialize_job(job, include_cells=False)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def read_rag_grid_job(
    job_id: uuid.UUID,
    _user_id: Optional[str],
    plan: PlanContext,
    db: Session,
) -> RagGridJobResponse:
    del _user_id  # reserved for future per-user scoping
    try:
        job = rag_grid.get_grid_job(db, job_id, include_cells=True)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grid_job_not_found") from None
    return rag_grid.serialize_job(job, include_cells=True)

__all__ = [
    "resolve_rag_deeplink",
    "record_rag_telemetry",
    "query_rag",
    "query_rag_stream",
    "query_rag_v2",
    "query_rag_grid",
    "create_rag_grid_job",
    "read_rag_grid_job",
]





