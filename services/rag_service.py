"""Business logic helpers for the Interactive Analyst (RAG) module."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from copy import deepcopy
import os
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Mapping

from pydantic import BaseModel
from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
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
from schemas.router import RouteDecision, RouteAction, SafetyDecision, ToolCall, UiContainer, PaywallTier
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
    snapshot_service,
)
from services.agent_tools.event_study_tool import (
    EventStudyNotFoundError,
    generate_event_study_payload,
)
from services.audit_log import audit_rag_event
from services.semantic_router import DEFAULT_ROUTER
from services.user_settings_service import UserLightMemSettings
from services.rag_shared import build_anchor_payload, normalize_reliability, safe_float, safe_int
from models.chat import ChatMessage, ChatSession
from models.event_study import EventRecord
from models.filing import Filing
from models.summary import Summary
from services.memory.facade import MEMORY_SERVICE
from services.plan_service import PlanContext
import services.rag_metrics as rag_metrics
from services.widgets.factory import generate_widgets
from services.quota_guard import evaluate_quota
from services.tool_registry import resolve_tool_by_call_name
from services import snapshot_service

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


def _build_news_entry(chunk: Dict[str, Any], fallback_score: Optional[float] = None) -> Optional[Dict[str, Any]]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    summary = metadata.get("summary") or chunk.get("quote") or chunk.get("content")
    if not summary:
        return None

    def _first(*values: Any) -> Optional[str]:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    published_at = _first(metadata.get("published_at"), chunk.get("filed_at"), chunk.get("published_at"))
    url = _first(metadata.get("viewer_url"), metadata.get("article_url"), chunk.get("viewer_url"))
    sentiment_label = _first(metadata.get("sentiment"), chunk.get("sentiment"))
    sentiment_score = chunk.get("sentiment_score") or metadata.get("sentiment_score")

    return {
        "id": _first(chunk.get("chunk_id"), chunk.get("id"), metadata.get("source_id")),
        "title": _first(metadata.get("title"), chunk.get("title")),
        "source": _first(metadata.get("publisher"), chunk.get("publisher"), metadata.get("source")),
        "summary": summary,
        "sentiment": sentiment_label,
        "sentimentScore": float(sentiment_score) if isinstance(sentiment_score, (int, float)) else None,
        "publishedAt": published_at,
        "url": url,
        "ticker": metadata.get("ticker") or chunk.get("ticker"),
        "score": float(fallback_score) if isinstance(fallback_score, (int, float)) else safe_float(chunk.get("score")),
    }


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
        source_id = metadata.get("document_id") or metadata.get("source_id") or chunk.get("document_id")
        published_date = metadata.get("published_at") or metadata.get("filed_at") or chunk.get("filed_at")
        relevance_score = safe_float(chunk.get("score"))

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
        source_meta = {
            "document_id": source_id,
            "document_title": document_title,
            "page_number": safe_int(page_number),
            "url": viewer_url or download_url or document_url,
            "published_date": published_date,
        }
        entry["source_metadata"] = {k: v for k, v in source_meta.items() if v is not None}
        if relevance_score is not None:
            entry["relevance_score"] = relevance_score
        table_hint = _table_hint(metadata, safe_int(page_number))
        if table_hint:
            entry["table_hint"] = table_hint
        evidence.append(entry)
    return evidence


def _build_sources_payload(context: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for item in context or []:
        if not isinstance(item, dict):
            continue
        source_meta = item.get("source_metadata") if isinstance(item.get("source_metadata"), dict) else {}
        title = (
            item.get("document_title")
            or source_meta.get("document_title")
            or item.get("title")
            or item.get("source")
            or "출처"
        )
        page_number = safe_int(item.get("page_number") or item.get("page") or source_meta.get("page_number"))
        page_label = f"p.{page_number}" if page_number is not None else None
        snippet = item.get("quote") or item.get("content") or item.get("summary")
        source_url = (
            item.get("viewer_url")
            or item.get("download_url")
            or item.get("document_url")
            or source_meta.get("url")
        )
        rel_score = safe_float(
            item.get("relevance_score") or source_meta.get("relevance_score") or source_meta.get("score")
        )
        published_date = source_meta.get("published_date") or item.get("published_at") or item.get("created_at")
        sources.append(
            {
                "id": item.get("urn_id") or item.get("chunk_id"),
                "title": title,
                "page": page_number,
                "pageLabel": page_label,
                "snippet": snippet,
                "sourceUrl": source_url,
                "type": item.get("source_type") or item.get("sourceType"),
                "score": rel_score if rel_score is not None else safe_float(item.get("score")),
                "publishedAt": published_date,
                "documentId": source_meta.get("document_id"),
            }
        )
    return sources


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
_QUOTA_PROBLEM_TYPE = "https://nuvien.com/docs/errors/plan-quota"
_CHAT_ACTION_LABEL = "AI 분석"
_PROFILE_SESSION_PREFIX = "user:"


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

NO_CONTEXT_ANSWER = (
    "문의하신 내용과 직접적으로 연결된 증거를 찾지 못했습니다. "
    "좀 더 구체적인 기업명·티커·기간을 포함해 다시 질문해 보시겠어요? "
    "예: “삼성전자 2023 3분기 실적 요약”, “2차전지 섹터 IRA 변수 영향 요약”."
)
INTENT_GENERAL_MESSAGE = "요청하신 내용은 정책상 바로 제공되지 않습니다. 보다 구체적인 배경이나 합법적 목적을 함께 알려 주세요."
INTENT_BLOCK_MESSAGE = SAFE_MESSAGE
INTENT_WARNING_CODE = "intent_filter"
FRONT_DOOR_WARNING_CODE = "front_door_guard"
FRONT_DOOR_CHITCHAT_REPLY = (
    "안녕하세요, 저는 금융·투자 분석에 특화된 Nuvien AI Copilot입니다. "
    "기업 실적, 시장 동향, 경제 지표 같은 질문에 집중해 답변드릴게요. 궁금한 티커나 산업이 있으신가요?"
)
try:
    _MIN_RELEVANCE_RAW = float(os.getenv("RAG_MIN_RELEVANCE", "0"))
    RAG_MIN_RELEVANCE = max(0.0, min(1.0, _MIN_RELEVANCE_RAW))
except Exception:
    RAG_MIN_RELEVANCE = 0.0


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID header.") from exc


def _normalize_context_ids(value: Any) -> Dict[str, str]:
    """Extract stable context identifiers (company/filing/event) from arbitrary metadata."""

    if not isinstance(value, dict):
        return {}

    candidates = {
        "company_id": [
            value.get("company_id"),
            value.get("company"),
            value.get("ticker"),
            value.get("corp_code"),
            value.get("corpCode"),
        ],
        "filing_id": [
            value.get("filing_id"),
            value.get("filingId"),
            value.get("receipt_no"),
            value.get("receiptNo"),
            value.get("report_code"),
        ],
        "event_id": [
            value.get("event_id"),
            value.get("eventId"),
            value.get("rcept_no"),
            value.get("event"),
        ],
    }

    normalized: Dict[str, str] = {}
    for key, values in candidates.items():
        for candidate in values:
            if candidate is None:
                continue
            text = str(candidate).strip()
            if text:
                normalized[key] = text
                break
    return normalized


def _stringify_number(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"{value}"
    except Exception:
        return None


def _load_company_context_chunk(identifier: Optional[str], db: Session) -> Optional[Dict[str, Any]]:
    if not identifier:
        return None
    try:
        snapshot = snapshot_service.get_company_snapshot(identifier, db=db)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.debug("Company snapshot prefetch failed for %s: %s", identifier, exc)
        return None

    if not isinstance(snapshot, dict):
        return None

    corp_label = snapshot.get("corp_name") or snapshot.get("ticker") or identifier
    summary_block = snapshot.get("summary") or {}
    latest = snapshot.get("latest_filing") or {}
    lines: List[str] = []
    if latest:
        label = latest.get("report_name") or latest.get("title") or latest.get("receipt_no")
        filed_at = latest.get("filed_at")
        if label:
            lines.append(f"최근 공시: {label} ({filed_at})")
    for key in ("insight", "why", "what", "who"):
        text = summary_block.get(key)
        if isinstance(text, str) and text.strip():
            lines.append(text.strip())
            break
    metrics = snapshot.get("key_metrics") or []
    if isinstance(metrics, list) and metrics:
        top_metrics = []
        for metric in metrics[:3]:
            if not isinstance(metric, dict):
                continue
            label = metric.get("label") or metric.get("name")
            value = metric.get("value") or metric.get("formatted_value")
            if label and value:
                top_metrics.append(f"{label}: {value}")
        if top_metrics:
            lines.append("주요 지표 - " + "; ".join(top_metrics))

    content = "\n".join(lines) if lines else f"{corp_label} 최신 스냅샷"
    return {
        "id": f"ctx:company:{identifier}",
        "chunk_id": f"ctx:company:{identifier}",
        "source_type": "snapshot",
        "doc_type": "snapshot",
        "ticker": snapshot.get("ticker") or identifier,
        "corp_name": snapshot.get("corp_name"),
        "filing_id": latest.get("receipt_no"),
        "filed_at": latest.get("filed_at"),
        "section": "company_snapshot",
        "title": f"{corp_label} 스냅샷",
        "content": content,
        "score": 1.2,
    }


def _load_filing_context_chunk(filing_identifier: Optional[str], db: Session) -> Optional[Dict[str, Any]]:
    if not filing_identifier:
        return None

    filing = None
    try:
        filing_uuid = uuid.UUID(filing_identifier)
    except Exception:
        filing_uuid = None

    if filing_uuid:
        filing = (
            db.query(Filing)
            .filter(Filing.id == filing_uuid)
            .first()
        )
    if filing is None:
        filing = (
            db.query(Filing)
            .filter(or_(Filing.receipt_no == filing_identifier, Filing.report_code == filing_identifier))
            .first()
        )
    if filing is None:
        return None

    summary = (
        db.query(Summary)
        .filter(Summary.filing_id == filing.id)
        .order_by(Summary.created_at.desc())
        .first()
    )

    lines: List[str] = []
    if filing.report_name or filing.title:
        lines.append(f"{filing.report_name or ''} {filing.title or ''}".strip())
    if filing.filed_at:
        lines.append(f"제출일자: {filing.filed_at.isoformat()}")
    if summary:
        for key in ("insight", "what", "why", "how"):
            text = getattr(summary, key, None)
            if isinstance(text, str) and text.strip():
                lines.append(text.strip())
                break

    content = "\n".join(lines) if lines else "요약 정보가 없습니다."
    return {
        "id": f"ctx:filing:{filing.id}",
        "chunk_id": f"ctx:filing:{filing.id}",
        "source_type": "filing",
        "doc_type": "filing",
        "ticker": filing.ticker,
        "corp_name": filing.corp_name,
        "filing_id": str(filing.id),
        "receipt_no": filing.receipt_no,
        "section": filing.category or "filing",
        "title": filing.report_name or filing.title or filing.receipt_no,
        "content": content,
        "score": 1.3,
    }


def _load_event_context_chunk(event_id: Optional[str], db: Session) -> Optional[Dict[str, Any]]:
    if not event_id:
        return None
    event = (
        db.query(EventRecord)
        .filter(EventRecord.rcept_no == event_id)
        .first()
    )
    if event is None:
        return None

    lines = [f"{event.event_type} 이벤트", event.corp_name or event.ticker or ""]
    if event.event_date:
        lines.append(f"발생일: {event.event_date.isoformat()}")
    if event.amount:
        amount = _stringify_number(event.amount)
        if amount:
            lines.append(f"규모: {amount}")
    if event.metadata and isinstance(event.metadata, dict):
        summary = event.metadata.get("summary")
        if isinstance(summary, str) and summary.strip():
            lines.append(summary.strip())

    return {
        "id": f"ctx:event:{event.rcept_no}",
        "chunk_id": f"ctx:event:{event.rcept_no}",
        "source_type": "event",
        "doc_type": "event",
        "ticker": event.ticker,
        "corp_name": event.corp_name,
        "filing_id": event.rcept_no,
        "section": event.event_type,
        "title": event.event_type,
        "content": "\n".join([line for line in lines if line]) or event.event_type,
        "score": 1.1,
    }


def _prefetch_context_chunks(context_ids: Dict[str, str], db: Session) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    filing_chunk = _load_filing_context_chunk(context_ids.get("filing_id"), db)
    if filing_chunk:
        chunks.append(filing_chunk)
    company_chunk = _load_company_context_chunk(context_ids.get("company_id"), db)
    if company_chunk:
        chunks.append(company_chunk)
    event_chunk = _load_event_context_chunk(context_ids.get("event_id"), db)
    if event_chunk:
        chunks.append(event_chunk)
    return chunks


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


def search_news_summaries(
    query: str,
    *,
    ticker: Optional[str] = None,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    normalized_query = (query or "").strip()
    if not normalized_query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query is required")

    limit = max(1, min(limit, 20))
    filters: Dict[str, Any] = {"source_type": "news"}
    if ticker:
        filters["ticker"] = ticker.strip()

    try:
        base_result = vector_service.query_vector_store(
            normalized_query,
            top_k=1,
            max_filings=limit,
            filters=filters,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("News vector search failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "news_rag_unavailable", "message": "뉴스 검색이 지연되고 있습니다. 잠시 후 다시 시도해 주세요."},
        ) from exc

    ranked_docs = list(base_result.related_filings or [])
    entries: List[Dict[str, Any]] = []

    for doc in ranked_docs:
        if len(entries) >= limit:
            break
        filing_id = str(doc.get("filing_id") or "")
        if not filing_id:
            continue
        chunks: List[Dict[str, Any]] = []
        if base_result.filing_id == filing_id and base_result.chunks:
            chunks = list(base_result.chunks)
        if not chunks:
            try:
                follow_up = vector_service.query_vector_store(
                    normalized_query,
                    filing_id=filing_id,
                    top_k=1,
                    max_filings=1,
                    filters=filters,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("News follow-up lookup failed for %s: %s", filing_id, exc)
                continue
            chunks = list(follow_up.chunks or [])
        if not chunks:
            continue
        entry = _build_news_entry(chunks[0], fallback_score=doc.get("score"))
        if entry:
            entries.append(entry)

    return entries


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
            "router_action": route_decision.tool_name,
            "router_intent": route_decision.intent,
            "router_decision": route_decision.model_dump_route(),
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
            "router_action": route_decision.tool_name,
            "router_intent": route_decision.intent,
            "router_decision": route_decision.model_dump_route(),
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


def _front_door_route_decision(category: str) -> RouteDecision:
    reason = f"{FRONT_DOOR_WARNING_CODE}:{category}"
    return RouteDecision(
        intent="front_door_guard",
        reason=reason,
        confidence=1.0,
        tool_call=ToolCall(name="front_door.guard", arguments={"category": category}),
        ui_container=UiContainer.INLINE_CARD,
        paywall=PaywallTier.FREE,
        requires_context=[],
        safety=SafetyDecision(block=False, reason=None, keywords=[]),
        tickers=[],
        metadata={"category": category, "source": "front_door_guard"},
    )


def _front_door_reply_text(category: str, question: str) -> str:
    if category == "chitchat":
        return FRONT_DOOR_CHITCHAT_REPLY
    preview = chat_service.trim_preview(question)
    topic_label = f"'{preview}'" if preview else "해당 질문"
    return (
        f"문의하신 {topic_label}은(는) 금융 및 투자 분석 범위를 벗어나는 주제입니다. "
        "저는 기업 실적, 시장 동향, 경제 지표 등에 대한 답변을 드리도록 설계되었습니다. "
        "분석이 필요한 기업이나 산업이 있으신가요?"
    )


def build_front_door_response(
    db: Session,
    *,
    category: str,
    question: str,
    trace_id: str,
    session: ChatSession,
    turn_id: uuid.UUID,
    user_message: ChatMessage,
    assistant_message: ChatMessage,
    conversation_memory: Optional[Dict[str, Any]],
    classifier_result: Dict[str, Any],
    route_decision: Optional[RouteDecision],
    memory_info: Optional[Dict[str, Any]] = None,
) -> Tuple[RAGQueryResponse, bool]:
    answer_text = _front_door_reply_text(category, question)
    warning_code = f"{FRONT_DOOR_WARNING_CODE}:{category}"
    conversation_summary = None
    recent_turn_count = 0
    if conversation_memory:
        conversation_summary = conversation_memory.get("summary")
        recent_turn_count = len(conversation_memory.get("recent_turns") or [])

    guardrail_meta = {
        "decision": warning_code,
        "reason": classifier_result.get("reason") or classifier_result.get("error"),
        "rag_mode": "none",
        "category": category,
        "model": classifier_result.get("model_used"),
    }

    meta_payload = {
        "model": classifier_result.get("model_used"),
        "prompt_version": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "cost": None,
        "retrieval": {"doc_ids": [], "hit_at_k": 0, "rag_mode": "none"},
        "guardrail": guardrail_meta,
        "turnId": str(turn_id),
        "traceId": trace_id,
        "citations": {"page": [], "table": [], "footnote": []},
        "conversation_summary": conversation_summary,
        "recent_turn_count": recent_turn_count,
        "answer_preview": chat_service.trim_preview(answer_text),
        "intent_decision": f"front_door:{category}",
        "intent_reason": classifier_result.get("reason"),
        "front_door": {
            "category": category,
            "model": classifier_result.get("model_used"),
            "error": classifier_result.get("error"),
        },
    }
    if route_decision:
        meta_payload["router_action"] = route_decision.tool_name
        meta_payload["router_intent"] = route_decision.intent
        meta_payload["router_decision"] = route_decision.model_dump_route()
        meta_payload["router_confidence"] = route_decision.confidence
    if memory_info is not None:
        meta_payload["memory"] = dict(memory_info)
    meta_payload["evidence_version"] = "v2"
    meta_payload["evidence_diff"] = {"enabled": False, "removed": []}

    chat_service.update_message_state(
        db,
        message_id=assistant_message.id,
        state="ready",
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
        warnings=[warning_code],
        highlights=[],
        error=None,
        original_answer=None,
        model_used=classifier_result.get("model_used"),
        trace_id=trace_id,
        judge_decision=None,
        judge_reason=classifier_result.get("reason"),
        meta=meta_payload,
        state="ready",
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
    tool_context_value = user_meta.get("tool_context")
    tool_context: Optional[str] = None
    if isinstance(tool_context_value, str):
        stripped = tool_context_value.strip()
        if stripped:
            tool_context = stripped
    user_settings = _load_user_lightmem_settings(user_id)
    plan_memory_enabled = _plan_memory_enabled(plan, user_settings=user_settings)
    if tool_context:
        prompt_metadata["tool_context"] = tool_context

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
    memory_info: Dict[str, Any] = {
        "enabled": False,
        "reason": "not_evaluated",
        "applied": False,
        "captured": False,
        "hydrated": False,
        "required": False,
    }

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


def _requires_lightmem(route_decision: RouteDecision) -> bool:
    contexts = route_decision.requires_context or []
    for ctx in contexts:
        if isinstance(ctx, str) and ctx.strip().lower() == "lightmem.summary":
            return True
    return False


def _should_call_event_study(route_decision: RouteDecision) -> bool:
    intent = (route_decision.intent or "").strip().lower()
    tool_name = (route_decision.tool_name or "").strip().lower()
    return intent == "event_study" or tool_name == "event_study.query"


def _parse_event_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.date()


def _extract_event_tool_args(
    ctx: "RagSessionStage",
    route_decision: RouteDecision,
) -> Tuple[Optional[str], Optional[date], Optional[int], Optional[str]]:
    args = route_decision.tool_call.arguments or {}
    ticker = args.get("ticker") or args.get("symbol")
    if not ticker:
        filters = ctx.filter_payload.get("ticker")
        if isinstance(filters, str):
            ticker = filters
    normalized_ticker = (str(ticker).strip().upper() if ticker else None)
    event_date = _parse_event_date(args.get("event_date") or args.get("eventDate"))
    window_value = safe_int(args.get("window"))
    window_key = args.get("window_key") or args.get("windowKey")
    return normalized_ticker, event_date, window_value, window_key


def _format_percent(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return None


def _build_event_study_chunk(payload: Dict[str, Any]) -> Dict[str, Any]:
    ticker = payload.get("ticker")
    event_type = payload.get("eventType")
    window_info = payload.get("window") or {}
    metrics = payload.get("metrics") or {}

    lines: List[str] = []
    header = f"[Event Study] {ticker or ''} {event_type or ''}".strip()
    lines.append(header)
    if window_info:
        label = window_info.get("label") or f"[{window_info.get('start')},{window_info.get('end')}]"
        lines.append(f"Window: {label} (p={window_info.get('significance')})")

    sample_size = metrics.get("sampleSize")
    mean_caar = _format_percent(metrics.get("meanCaar"))
    hit_rate = _format_percent(metrics.get("hitRate"))
    ci_low = _format_percent(metrics.get("ciLo"))
    ci_high = _format_percent(metrics.get("ciHi"))
    p_value = metrics.get("pValue")

    lines.append(f"Sample Size: {sample_size or 'N/A'}")
    lines.append(f"Mean CAAR: {mean_caar or 'N/A'}")
    lines.append(f"Hit Rate: {hit_rate or 'N/A'}")
    lines.append(f"Confidence Interval: {ci_low or '-'} ~ {ci_high or '-'}")
    lines.append(f"P-Value: {p_value if p_value is not None else 'N/A'}")

    detail = payload.get("eventDetail") or {}
    detail_title = detail.get("event_type") or detail.get("corp_name")
    if detail_title or detail.get("event_date"):
        lines.append(
            f"Primary Event: {detail_title or 'Unknown'} on {detail.get('event_date') or 'N/A'}"
        )

    recent_section = payload.get("recentEvents") or {}
    recent_events = []
    if isinstance(recent_section, dict):
        recent_events = recent_section.get("events") or []
    elif isinstance(recent_section, list):
        recent_events = recent_section
    for entry in recent_events[:3]:
        title = entry.get("title") or entry.get("corp_name") or "Peer Event"
        event_date_value = entry.get("event_date") or entry.get("eventDate") or entry.get("published_at")
        caar_value = _format_percent(entry.get("caar"))
        lines.append(f"- {event_date_value or 'N/A'} · {title}: CAAR {caar_value or 'N/A'}")

    chunk_id = f"event-study:{ticker or 'unknown'}:{payload.get('eventDate') or window_info.get('label') or 'latest'}"
    metadata = {
        "type": "event_study",
        "ticker": ticker,
        "event_type": event_type,
        "window": window_info,
        "metrics": metrics,
        "source": "event_study_tool",
    }
    return {
        "id": chunk_id,
        "type": "event_study",
        "content": "\n".join(lines),
        "section": "event_study",
        "source": "event_study_tool",
        "metadata": metadata,
    }


def _build_widget_attachments(question: str, answer_text: str, context: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Run widget generators and normalize payloads for chat meta."""

    try:
        attachments = generate_widgets(question, answer_text, context=context)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Widget generation failed: %s", exc, exc_info=True)
        return []

    normalized: List[Dict[str, Any]] = []
    for attachment in attachments:
        try:
            if hasattr(attachment, "model_dump"):
                normalized.append(attachment.model_dump(mode="json", exclude_none=True))
            else:
                normalized.append(dict(attachment))  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Skipping widget attachment due to serialization error: %s", exc)
            continue
    return normalized


def _maybe_run_event_study_tool(
    ctx: "RagSessionStage",
    route_decision: RouteDecision,
    db: Session,
) -> List[Dict[str, Any]]:
    if not _should_call_event_study(route_decision):
        return []
    ticker, event_date, window_value, window_key = _extract_event_tool_args(ctx, route_decision)
    if not ticker:
        return []
    tool_args = {
        "ticker": ticker,
        "event_date": event_date.isoformat() if isinstance(event_date, date) else event_date,
        "window": window_value,
        "window_key": window_key,
    }
    if ctx.session and ctx.turn_id:
        try:
            chat_service.create_tool_call_message(
                db,
                session_id=ctx.session.id,
                turn_id=ctx.turn_id,
                tool_name="event_study.query",
                arguments=tool_args,
                idempotency_key=ctx.idempotency_key,
            )
            db.flush()
        except Exception:
            # best effort; do not block main flow
            logger.debug("Failed to record event study tool_call", exc_info=True)
    try:
        payload = generate_event_study_payload(
            ticker=ticker,
            event_date=event_date,
            window=window_value,
            window_key=window_key,
            db=db,
        )
    except EventStudyNotFoundError as exc:
        logger.info("Event study tool skipped: %s", exc)
        return []
    except Exception as exc:  # pragma: no cover - analytics best-effort
        logger.warning("Event study tool failed for %s: %s", ticker, exc, exc_info=True)
        if ctx.session and ctx.turn_id:
            try:
                chat_service.create_tool_output_message(
                    db,
                    session_id=ctx.session.id,
                    turn_id=ctx.turn_id,
                    tool_name="event_study.query",
                    output={"error": "event_study_failed"},
                    status="error",
                    idempotency_key=ctx.idempotency_key,
                )
                db.flush()
            except Exception:
                logger.debug("Failed to record event study tool_output error", exc_info=True)
        return []
    chunk = _build_event_study_chunk(payload)
    if ctx.session and ctx.turn_id:
        try:
            chat_service.create_tool_output_message(
                db,
                session_id=ctx.session.id,
                turn_id=ctx.turn_id,
                tool_name="event_study.query",
                output={"event_study": payload, "chunk_id": chunk.get("id")},
                status="ok",
                idempotency_key=ctx.idempotency_key,
            )
            db.flush()
        except Exception:
            logger.debug("Failed to record event study tool_output", exc_info=True)
    return [chunk]


def _compose_lightmem_context(
    question: str,
    conversation_memory: Optional[Dict[str, Any]],
    *,
    session_key: str,
    tenant_id: Optional[str],
    user_id: Optional[str],
    plan_memory_enabled: bool,
    require_lightmem: bool,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    info: Dict[str, Any] = {
        "enabled": False,
        "required": require_lightmem,
        "hydrated": True,
        "applied": False,
        "captured": False,
    }
    if not require_lightmem:
        info["reason"] = "not_requested"
        return conversation_memory, info
    if not plan_memory_enabled:
        info["reason"] = "plan_disabled"
        return conversation_memory, info
    if not tenant_id or not user_id:
        info["reason"] = "missing_subject"
        return conversation_memory, info
    merged_memory, memory_info = rag_audit.merge_lightmem_context(
        question,
        conversation_memory,
        session_key=session_key,
        tenant_id=tenant_id,
        user_id=user_id,
        plan_memory_enabled=plan_memory_enabled,
    )
    memory_info.setdefault("required", True)
    memory_info["hydrated"] = True
    return merged_memory, memory_info


def _hydrate_lightmem_context(ctx: RagSessionStage, require_lightmem: bool) -> None:
    if ctx.memory_info.get("hydrated"):
        return
    conversation_memory, memory_info = _compose_lightmem_context(
        ctx.question,
        ctx.conversation_memory,
        session_key=ctx.memory_session_key,
        tenant_id=ctx.tenant_id_value,
        user_id=ctx.user_id_value,
        plan_memory_enabled=ctx.plan_memory_enabled,
        require_lightmem=require_lightmem,
    )
    ctx.conversation_memory = conversation_memory
    ctx.memory_info = memory_info


def _filter_chunks_by_relevance(chunks: List[Dict[str, Any]], *, threshold: float) -> List[Dict[str, Any]]:
    if threshold <= 0:
        return list(chunks)
    filtered: List[Dict[str, Any]] = []
    for chunk in chunks:
        score = safe_float(chunk.get("score"))
        if score is None or score >= threshold:
            filtered.append(chunk)
    return filtered


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
        context_chunks = _filter_chunks_by_relevance(retrieval.chunks, threshold=RAG_MIN_RELEVANCE)
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
    route_decision: RouteDecision,
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
        "router_action": route_decision.tool_name,
        "router_intent": route_decision.intent,
        "router_decision": route_decision.model_dump_route(),
    }
    if ctx.prompt_metadata:
        meta_payload["prompt"] = ctx.prompt_metadata
    meta_payload["evidence_version"] = "v2"
    meta_payload["evidence_diff"] = llm_stage.diff_meta
    meta_payload["sources"] = _build_sources_payload(llm_stage.context)
    widget_payload = _build_widget_attachments(ctx.question, llm_stage.answer_text, llm_stage.context)
    if widget_payload:
        meta_payload["toolAttachments"] = widget_payload

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
    # Capture lightweight per-user interest/profile hints (hidden personalization).
    if ctx.user_id:
        captured_profile = rag_audit.capture_user_interest_profile(
            question=ctx.question,
            answer=llm_stage.answer_text,
            session=ctx.session,
            tenant_id=ctx.tenant_id_value,
            user_id=str(ctx.user_id),
            plan_memory_enabled=ctx.plan_memory_enabled,
        )
        if captured_profile:
            ctx.memory_info["profile_captured"] = True
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
        classifier_result = llm_service.classify_query_category(question)
        front_category = classifier_result.get("category") or "financial_query"
        ctx.user_meta["front_door_category"] = front_category
        ctx.user_meta["front_door_model"] = classifier_result.get("model_used")

        if front_category == "financial_query":
            route_decision = _resolve_route_decision(route_decision, question)
        else:
            route_decision = _front_door_route_decision(front_category)
        ctx.user_meta["router_action"] = route_decision.tool_name
        ctx.user_meta["router_intent"] = route_decision.intent
        ctx.user_meta["router_decision"] = route_decision.model_dump_route()
        ctx.user_meta["router_confidence"] = route_decision.confidence

        route_payload = route_decision.model_dump_route()
        _hydrate_lightmem_context(ctx, _requires_lightmem(route_decision))
        conversation_memory = ctx.conversation_memory
        memory_info = ctx.memory_info
        if front_category != "financial_query":
            response, needs_summary = build_front_door_response(
                db,
                category=front_category,
                question=question,
                trace_id=trace_id,
                session=session,
                turn_id=turn_id,
                user_message=user_message,
                assistant_message=assistant_message,
                conversation_memory=conversation_memory,
                classifier_result=classifier_result,
                route_decision=route_decision,
                memory_info=memory_info,
            )
            db.commit()
            _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, session.id)
            return response

        intent_gate = _evaluate_intent_gate(
            ctx,
            route_decision,
            db,
            plan_memory_enabled=plan_memory_enabled,
        )
        if intent_gate.response:
            return intent_gate.response

        retrieval_stage = _run_retrieval_stage(ctx, request, db)
        event_chunks = _maybe_run_event_study_tool(ctx, route_decision, db)
        if event_chunks:
            retrieval_stage.context_chunks = event_chunks + retrieval_stage.context_chunks

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
            route_decision=intent_gate.route,
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
    question_text = getattr(request, "question", None) or getattr(request, "query", "")
    # Numeric-only shortcut: stream snapshot tool_call/tool_output
    if question_text and str(question_text).strip().isdigit():
        question = str(question_text).strip()
        turn_id = _coerce_uuid(request.turn_id)
        session_uuid = _parse_uuid(request.session_id)
        user_id = _resolve_lightmem_user_id(x_user_id)
        org_id = _parse_uuid(x_org_id)
        session = _resolve_session(
            db,
            session_id=session_uuid,
            user_id=user_id,
            org_id=org_id,
            filing_id=None,
        )
        user_message = _ensure_user_message(
            db,
            session=session,
            user_message_id=request.user_message_id,
            question=question,
            turn_id=turn_id,
            idempotency_key=idempotency_key_header,
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
        chat_service.create_tool_call_message(
            db,
            session_id=session.id,
            turn_id=turn_id,
            tool_name="snapshot.company",
            arguments={"ticker": question},
            idempotency_key=idempotency_key_header,
        )
        enqueue_state = snapshot_service.enqueue_company_snapshot_job(
            session_id=session.id,
            turn_id=turn_id,
            assistant_message_id=assistant_message.id,
            user_message_id=user_message.id,
            ticker=question,
            idempotency_key=idempotency_key_header,
            db=db,
        )
        chat_service.update_message_state(
            db,
            message_id=assistant_message.id,
            state="running",
            content="기업 스냅샷을 준비 중입니다...",
            meta={"tool_output": {"name": "snapshot.company", "status": enqueue_state}},
        )
        db.commit()

        def stream_snapshot():
            route_payload = {"tool_call": {"name": "snapshot.company", "arguments": {"ticker": question}}}
            yield json.dumps(
                {
                    "event": "route",
                    "id": str(assistant_message.id),
                    "turn_id": str(turn_id),
                    "decision": route_payload,
                }
            ) + "\n"
            yield json.dumps(
                {
                    "event": "chunk",
                    "id": str(assistant_message.id),
                    "turn_id": str(turn_id),
                    "delta": "기업 스냅샷 요청을 접수했습니다. 완료되면 결과를 보내드릴게요.",
                }
            ) + "\n"
            payload_json = {
                "answer": "기업 스냅샷을 준비 중입니다.",
                "sessionId": str(session.id),
                "turnId": str(turn_id),
                "userMessageId": str(user_message.id),
                "assistantMessageId": str(assistant_message.id),
                "traceId": str(uuid.uuid4()),
                "state": "running",
                "ragMode": "none",
                "meta": {"tool": "snapshot.company", "tool_status": enqueue_state},
            }
            yield json.dumps(
                {
                    "event": "done",
                    "id": str(assistant_message.id),
                    "turn_id": str(turn_id),
                    "payload": payload_json,
                }
            ) + "\n"

        return StreamingResponse(stream_snapshot(), media_type="text/event-stream")

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
        classifier_result = llm_service.classify_query_category(question)
        front_category = classifier_result.get("category") or "financial_query"
        ctx.user_meta["front_door_category"] = front_category
        ctx.user_meta["front_door_model"] = classifier_result.get("model_used")

        if front_category == "financial_query":
            route_decision = _resolve_route_decision(route_decision, question)
        else:
            route_decision = _front_door_route_decision(front_category)
        ctx.user_meta["router_action"] = route_decision.tool_name
        ctx.user_meta["router_intent"] = route_decision.intent
        ctx.user_meta["router_decision"] = route_decision.model_dump_route()
        ctx.user_meta["router_confidence"] = route_decision.confidence
        route_payload = route_decision.model_dump_route()
        _hydrate_lightmem_context(ctx, _requires_lightmem(route_decision))
        conversation_memory = ctx.conversation_memory
        memory_info = ctx.memory_info
        if front_category != "financial_query":
            response, needs_summary = build_front_door_response(
                db,
                category=front_category,
                question=question,
                trace_id=trace_id,
                session=session,
                turn_id=turn_id,
                user_message=user_message,
                assistant_message=assistant_message,
                conversation_memory=conversation_memory,
                classifier_result=classifier_result,
                route_decision=route_decision,
                memory_info=memory_info,
            )
            db.commit()
            _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, session.id)
            payload_json = response.model_dump(mode="json")
            def front_door_stream():
                yield json.dumps(
                    {
                        "event": "route",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "decision": route_payload,
                    }
                ) + "\n"
                yield json.dumps(
                    {
                        "event": "done",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "payload": payload_json,
                    }
                ) + "\n"

            return StreamingResponse(front_door_stream(), media_type="text/event-stream")
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
                        "event": "route",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "decision": route_payload,
                    }
                ) + "\n"
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
        context_chunks = _filter_chunks_by_relevance(pipeline_result.raw_chunks, threshold=RAG_MIN_RELEVANCE)
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
                        "event": "route",
                        "id": str(assistant_message.id),
                        "turn_id": str(turn_id),
                        "decision": route_payload,
                    }
                ) + "\n"
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
                    "event": "route",
                    "id": str(assistant_message.id),
                    "turn_id": str(turn_id),
                    "decision": route_payload,
                }
            ) + "\n"
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
                    route_decision=route_decision,
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

    # Shortcut: numeric-only input interpreted as ticker -> trigger snapshot tool flow
    if question.isdigit():
        turn_id = _coerce_uuid(payload.turnId)
        session_uuid = _parse_uuid(payload.sessionId)
        user_id = _resolve_lightmem_user_id(x_user_id)
        org_id = _parse_uuid(x_org_id)

        session = _resolve_session(
            db,
            session_id=session_uuid,
            user_id=user_id,
            org_id=org_id,
            filing_id=None,
        )
        user_message = _ensure_user_message(
            db,
            session=session,
            user_message_id=_parse_uuid(payload.userMessageId),
            question=question,
            turn_id=turn_id,
            idempotency_key=payload.idempotencyKey,
            meta=payload.meta or {},
        )
        assistant_message = _ensure_assistant_message(
            db,
            session=session,
            assistant_message_id=_parse_uuid(payload.assistantMessageId),
            turn_id=turn_id,
            idempotency_key=None,
            retry_of_message_id=_parse_uuid(payload.retryOfMessageId),
            initial_state="pending",
        )
        chat_service.create_tool_call_message(
            db,
            session_id=session.id,
            turn_id=turn_id,
            tool_name="snapshot.company",
            arguments={"ticker": question},
            idempotency_key=payload.idempotencyKey,
        )
        enqueue_state = snapshot_service.enqueue_company_snapshot_job(
            session_id=session.id,
            turn_id=turn_id,
            assistant_message_id=assistant_message.id,
            user_message_id=user_message.id,
            ticker=question,
            idempotency_key=payload.idempotencyKey,
            db=db,
        )
        chat_service.update_message_state(
            db,
            message_id=assistant_message.id,
            state="running",
            content="기업 스냅샷을 준비 중입니다...",
            meta={"tool_output": {"name": "snapshot.company", "status": enqueue_state}},
        )
        db.commit()

        return RagQueryV2Response(
            answer="기업 스냅샷을 준비 중입니다.",
            evidence=[],
            warnings=[],
            citations={},
            sessionId=str(session.id),
            turnId=str(turn_id),
            userMessageId=str(user_message.id),
            assistantMessageId=str(assistant_message.id),
            traceId=str(uuid.uuid4()),
            state="running",
            ragMode="none",
            meta={"tool": "snapshot.company", "tool_status": enqueue_state},
        )

    classifier_result = llm_service.classify_query_category(question)
    front_category = classifier_result.get("category") or "financial_query"
    if front_category == "financial_query":
        route_decision = _resolve_route_decision(route_decision, question)
    else:
        route_decision = _front_door_route_decision(front_category)
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
    user_meta.setdefault("front_door_category", front_category)
    if classifier_result.get("model_used"):
        user_meta.setdefault("front_door_model", classifier_result.get("model_used"))
    user_meta.setdefault("router_action", route_decision.tool_name)
    user_meta.setdefault("router_intent", route_decision.intent)
    user_meta.setdefault("router_decision", route_decision.model_dump_route())
    user_meta.setdefault("router_confidence", route_decision.confidence)
    context_ids = _normalize_context_ids(user_meta.get("context_ids"))
    if context_ids:
        user_meta["context_ids"] = context_ids
        if context_ids.get("company_id"):
            if context_ids["company_id"] not in payload.tickers:
                payload.tickers.insert(0, context_ids["company_id"])
            if context_ids["company_id"] not in payload.filters.tickers:
                payload.filters.tickers.insert(0, context_ids["company_id"])
        if context_ids.get("filing_id") and not payload.filingId:
            payload.filingId = context_ids["filing_id"]
    else:
        context_ids = {}
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
        conversation_memory, memory_info = _compose_lightmem_context(
            question,
            conversation_memory,
            session_key=memory_session_key,
            tenant_id=tenant_id_value,
            user_id=user_id_value,
            plan_memory_enabled=plan_memory_enabled,
            require_lightmem=_requires_lightmem(route_decision),
        )

        if front_category != "financial_query":
            response, needs_summary = build_front_door_response(
                db,
                category=front_category,
                question=question,
                trace_id=trace_id,
                session=session,
                turn_id=turn_id,
                user_message=user_message,
                assistant_message=assistant_message,
                conversation_memory=conversation_memory,
                classifier_result=classifier_result,
                route_decision=route_decision,
                memory_info=memory_info,
            )
            db.commit()
            _enqueue_session_summary_if_allowed(plan_memory_enabled, needs_summary, session.id)
            return response

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

        prefetched_chunks = _prefetch_context_chunks(context_ids, db) if context_ids else []

        try:
            pipeline_result = rag_pipeline.run_rag_query(db, payload)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "rag.pipeline_unavailable", "message": "RAG 파이프라인을 잠시 사용할 수 없습니다. 잠시 후 다시 시도해 주세요."},
            ) from exc

        if prefetched_chunks:
            pipeline_result.raw_chunks = prefetched_chunks + pipeline_result.raw_chunks

        filtered_chunks = _filter_chunks_by_relevance(pipeline_result.raw_chunks, threshold=RAG_MIN_RELEVANCE)
        llm_payload = llm_service.generate_rag_answer(
            question,
            filtered_chunks,
            judge_result=judge_result,
            prompt_metadata=prompt_metadata,
        )
        payload_rag_mode = llm_payload.get("rag_mode") or rag_mode_hint or "vector"

        context_chunks = filtered_chunks
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
        if context_ids:
            meta_payload.setdefault("context_ids", context_ids)
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
            "memory": memory_info,
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
    "search_news_summaries",
]





