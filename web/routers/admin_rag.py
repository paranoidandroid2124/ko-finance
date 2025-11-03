"""Admin RAG configuration endpoints backed by persistent storage."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

import llm.llm_service as llm_service
from schemas.api.admin import (
    AdminRagConfigResponse,
    AdminRagConfigSchema,
    AdminRagConfigUpdateRequest,
    AdminRagFilterSchema,
    AdminRagReindexRequest,
    AdminRagReindexResponse,
    AdminRagReindexHistoryResponse,
    AdminRagReindexRecordSchema,
    AdminRagReindexQueueEntrySchema,
    AdminRagReindexQueueResponse,
    AdminRagReindexRetryRequest,
    AdminRagReindexRetryResponse,
    AdminRagSourceSchema,
)
from services import admin_rag_service, vector_service
from core.logging import get_logger
from web.deps_admin import require_admin_session

router = APIRouter(
    prefix="/admin/rag",
    tags=["Admin RAG"],
    dependencies=[Depends(require_admin_session)],
)

_AUDIT_DIR = Path("uploads") / "admin"
logger = get_logger(__name__)

def _to_config_schema(raw: Dict[str, object]) -> AdminRagConfigSchema:
    sources: List[AdminRagSourceSchema] = []
    for item in raw.get("sources", []):
        if isinstance(item, dict):
            try:
                sources.append(AdminRagSourceSchema(**item))
            except Exception:
                continue

    filters: List[AdminRagFilterSchema] = []
    for item in raw.get("filters", []):
        if isinstance(item, dict):
            try:
                filters.append(AdminRagFilterSchema(**item))
            except Exception:
                continue

    return AdminRagConfigSchema(
        sources=sources,
        filters=filters,
        similarityThreshold=float(raw.get("similarityThreshold", 0.0)),
        rerankModel=raw.get("rerankModel"),
        updatedAt=raw.get("updatedAt"),
        updatedBy=raw.get("updatedBy"),
    )


def _normalize_sources(sources: Optional[Iterable[str]]) -> List[str]:
    if not sources:
        return []
    normalized: List[str] = []
    seen: set[str] = set()
    for item in sources:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _perform_reindex(
    *,
    actor: str,
    sources: Iterable[str],
    note: Optional[str],
    queue_id: Optional[str] = None,
    retry_entry: Optional[Dict[str, object]] = None,
    retry_mode: str = "manual",
    rag_mode: Optional[str] = None,
) -> AdminRagReindexResponse:
    normalized_sources = _normalize_sources(sources)
    scope_list = normalized_sources or ["all"]
    scope_value = ",".join(scope_list)
    task_id = f"rag-reindex-{uuid.uuid4().hex[:12]}"
    langfuse_span = None
    langfuse_trace_url: Optional[str] = None
    langfuse_trace_id: Optional[str] = None
    langfuse_span_id: Optional[str] = None
    if retry_entry:
        langfuse_trace_url = retry_entry.get("langfuseTraceUrl") or None
        langfuse_trace_id = retry_entry.get("langfuseTraceId") or None
        langfuse_span_id = retry_entry.get("langfuseSpanId") or None

    metadata_payload: Dict[str, object] = {
        "taskId": task_id,
        "status": "queued",
        "retryMode": retry_mode,
        "ragMode": rag_mode or "vector",
        "scope": scope_value,
        "scopeDetail": scope_list,
    }
    input_payload: Dict[str, object] = {
        "taskId": task_id,
        "actor": actor,
        "sources": scope_list,
        "retryMode": retry_mode,
    }
    if queue_id:
        metadata_payload["queueId"] = queue_id
        input_payload["queueId"] = queue_id
    if retry_entry and retry_entry.get("langfuseTraceId"):
        metadata_payload["previousTraceId"] = retry_entry.get("langfuseTraceId")
    if retry_entry and retry_entry.get("langfuseSpanId"):
        metadata_payload["previousSpanId"] = retry_entry.get("langfuseSpanId")

    if llm_service.LANGFUSE_CLIENT:
        try:
            langfuse_span = llm_service.LANGFUSE_CLIENT.start_span(
                name="admin_rag_reindex",
                input=input_payload,
                metadata=metadata_payload,
            )
            langfuse_trace_id = getattr(langfuse_span, "trace_id", None) or langfuse_trace_id
            langfuse_span_id = getattr(langfuse_span, "span_id", None) or langfuse_span_id
            if langfuse_trace_id:
                try:
                    langfuse_trace_url = llm_service.LANGFUSE_CLIENT.get_trace_url(trace_id=langfuse_trace_id)
                except Exception:  # pragma: no cover - best-effort
                    pass
            if hasattr(langfuse_span, "create_event"):
                langfuse_span.create_event(name="queued", metadata={"status": "queued"})
        except Exception as exc:  # pragma: no cover - observability best-effort
            logger.debug("Langfuse span initialisation skipped: %s", exc, exc_info=True)
            langfuse_span = None

    if queue_id:
        admin_rag_service.update_retry_entry(queue_id, status="retrying")

    admin_rag_service.append_reindex_history(
        task_id=task_id,
        actor=actor,
        scope=scope_value,
        status="queued",
        note=note,
        langfuse_trace_url=langfuse_trace_url,
        langfuse_trace_id=langfuse_trace_id,
        langfuse_span_id=langfuse_span_id,
        queue_id=queue_id,
        retry_mode=retry_mode,
        rag_mode=rag_mode or "vector",
        scope_detail=scope_list,
    )

    started_at = datetime.now(timezone.utc)
    admin_rag_service.append_reindex_history(
        task_id=task_id,
        actor=actor,
        scope=scope_value,
        status="running",
        note=note,
        started_at=started_at.isoformat(),
        langfuse_trace_url=langfuse_trace_url,
        langfuse_trace_id=langfuse_trace_id,
        langfuse_span_id=langfuse_span_id,
        queue_id=queue_id,
        retry_mode=retry_mode,
        rag_mode=rag_mode or "vector",
        scope_detail=scope_list,
    )

    if queue_id:
        attempts = (retry_entry.get("attempts") if retry_entry else 0) or 0
        admin_rag_service.update_retry_entry(
            queue_id,
            status="running",
            attempts=attempts + 1,
            lastTaskId=task_id,
            lastAttemptAt=started_at.isoformat(),
            lastError=None,
        )

    if langfuse_span:
        try:
            langfuse_span.update(metadata={"taskId": task_id, "status": "running"})
            if hasattr(langfuse_span, "create_event"):
                langfuse_span.create_event(name="running", metadata={"status": "running"})
        except Exception as exc:  # pragma: no cover
            logger.debug("Langfuse running event skipped: %s", exc, exc_info=True)

    try:
        vector_service.init_collection()
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        error_code = getattr(exc, "detail", None) if isinstance(exc, HTTPException) else exc.__class__.__name__
        failure_note = f"{note or ''} :: {exc}".strip()
        admin_rag_service.append_reindex_history(
            task_id=task_id,
            actor=actor,
            scope=scope_value,
            status="failed",
            note=failure_note,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_ms=duration_ms,
            error_code=error_code,
            langfuse_trace_url=langfuse_trace_url,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_span_id=langfuse_span_id,
            queue_id=queue_id,
            retry_mode=retry_mode,
            rag_mode=rag_mode or "vector",
            scope_detail=scope_list,
        )
        if langfuse_span:
            try:
                langfuse_span.update(
                    metadata={"taskId": task_id, "status": "failed"},
                    status_message=str(exc),
                )
                if hasattr(langfuse_span, "create_event"):
                    langfuse_span.create_event(name="failed", metadata={"status": "failed", "error": str(exc)})
                langfuse_span.end()
                llm_service.LANGFUSE_CLIENT.flush()
            except Exception as span_exc:  # pragma: no cover
                logger.debug("Langfuse failure logging skipped: %s", span_exc, exc_info=True)
        if queue_id:
            admin_rag_service.update_retry_entry(
                queue_id,
                status="failed",
                lastError=str(exc),
                lastTaskId=task_id,
            )
        else:
            admin_rag_service.enqueue_retry_entry(
                original_task_id=task_id,
                scope=scope_value,
                actor=actor,
                note=note,
                error_code=error_code,
                langfuse_trace_url=langfuse_trace_url,
                langfuse_trace_id=langfuse_trace_id,
                langfuse_span_id=langfuse_span_id,
                retry_mode="auto",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.rag_reindex_failed", "message": str(exc)},
        ) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    evidence_diff = admin_rag_service.collect_evidence_diff(
        started_at=started_at,
        finished_at=finished_at,
        scope_detail=scope_list,
    )

    admin_rag_service.append_reindex_history(
        task_id=task_id,
        actor=actor,
        scope=scope_value,
        status="completed",
        note=note,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_ms=duration_ms,
        langfuse_trace_url=langfuse_trace_url,
        langfuse_trace_id=langfuse_trace_id,
        langfuse_span_id=langfuse_span_id,
        queue_id=queue_id,
        retry_mode=retry_mode,
        rag_mode=rag_mode or "vector",
        scope_detail=scope_list,
        evidence_diff=evidence_diff if evidence_diff and evidence_diff.get("totalChanges") else evidence_diff,
    )

    if langfuse_span:
        try:
            langfuse_span.update(
                metadata={"taskId": task_id, "status": "completed", "durationMs": duration_ms},
                output={"status": "completed", "durationMs": duration_ms},
            )
            if hasattr(langfuse_span, "create_event"):
                langfuse_span.create_event(
                    name="completed",
                    metadata={"status": "completed", "durationMs": duration_ms},
                )
            langfuse_span.end()
            llm_service.LANGFUSE_CLIENT.flush()
        except Exception as span_exc:  # pragma: no cover
            logger.debug("Langfuse completion logging skipped: %s", span_exc, exc_info=True)

    if queue_id:
        admin_rag_service.update_retry_entry(
            queue_id,
            status="completed",
            lastError=None,
            lastTaskId=task_id,
            lastSuccessAt=finished_at.isoformat(),
        )

    return AdminRagReindexResponse(taskId=task_id, status="completed")
@router.get(
    "/config",
    response_model=AdminRagConfigResponse,
    summary="현행 적용된 RAG 설정을 조회합니다.",
)
def read_rag_config() -> AdminRagConfigResponse:
    payload = admin_rag_service.load_rag_config()
    return AdminRagConfigResponse(config=_to_config_schema(payload))

@router.put(
    "/config",
    response_model=AdminRagConfigResponse,
    summary="RAG 설정을 업데이트합니다.",
)
def update_rag_config(payload: AdminRagConfigUpdateRequest) -> AdminRagConfigResponse:
    record = admin_rag_service.update_rag_config(
        sources=[source.model_dump() for source in payload.sources],
        filters=[filter_item.model_dump() for filter_item in payload.filters],
        similarity_threshold=payload.similarityThreshold,
        rerank_model=payload.rerankModel,
        actor=payload.actor,
        note=payload.note,
    )
    return AdminRagConfigResponse(config=_to_config_schema(record))

@router.post(
    "/reindex",
    response_model=AdminRagReindexResponse,
    summary="선택한 소스로 RAG 재색인을 요청합니다.",
)
def trigger_rag_reindex(payload: AdminRagReindexRequest) -> AdminRagReindexResponse:
    sources = payload.sources or []
    return _perform_reindex(actor=payload.actor, sources=sources, note=payload.note)


@router.get(
    "/reindex/history",
    response_model=AdminRagReindexHistoryResponse,
    summary="최근 RAG 재색인 이력을 조회합니다.",
)
def read_rag_reindex_history(
    limit: int = Query(50, ge=1, le=500),
    status: Optional[List[str]] = Query(default=None),
    search: Optional[str] = Query(default=None, alias="q"),
) -> AdminRagReindexHistoryResponse:
    history_raw = admin_rag_service.list_reindex_history(limit=limit)
    if status:
        allowed = {value.lower() for value in status if value}
        history_raw = [
            item
            for item in history_raw
            if str(item.get("status") or "").lower() in allowed
        ]
    if search:
        needle = search.lower()

        def _matches(record: Dict[str, object]) -> bool:
            for field in (
                "taskId",
                "actor",
                "scope",
                "note",
                "errorCode",
                "langfuseTraceUrl",
                "langfuseTraceId",
                "queueId",
            ):
                value = record.get(field)
                if isinstance(value, str) and needle in value.lower():
                    return True
            return False

        history_raw = [item for item in history_raw if _matches(item)]

    summary_payload = admin_rag_service.summarize_reindex_history(history_raw)
    runs: List[AdminRagReindexRecordSchema] = []
    for item in history_raw:
        try:
            runs.append(AdminRagReindexRecordSchema(**item))
        except Exception:
            continue
    return AdminRagReindexHistoryResponse(runs=runs, summary=summary_payload)


@router.get(
    "/reindex/queue",
    response_model=AdminRagReindexQueueResponse,
    summary="재색인 재시도 큐를 조회합니다.",
)
def read_rag_reindex_queue(
    status: Optional[List[str]] = Query(default=None),
    search: Optional[str] = Query(default=None, alias="q"),
) -> AdminRagReindexQueueResponse:
    queue_raw = admin_rag_service.load_retry_queue()
    if status:
        allowed = {item.lower() for item in status if item}
        queue_raw = [
            entry
            for entry in queue_raw
            if str(entry.get("status") or "").lower() in allowed
        ]
    if search:
        needle = search.lower()

        def _matches(entry: Dict[str, object]) -> bool:
            for field in (
                "queueId",
                "originalTaskId",
                "scope",
                "actor",
                "note",
                "lastError",
                "langfuseTraceUrl",
                "langfuseTraceId",
            ):
                value = entry.get(field)
                if isinstance(value, str) and needle in value.lower():
                    return True
            return False

        queue_raw = [entry for entry in queue_raw if _matches(entry)]

    summary_payload = admin_rag_service.summarize_retry_queue(queue_raw)
    entries: List[AdminRagReindexQueueEntrySchema] = []
    for item in queue_raw:
        try:
            payload = dict(item)
            payload.setdefault("retryMode", (payload.get("retryMode") or "auto"))
            cooldown_until = admin_rag_service.compute_next_retry_time(
                payload,
                cooldown_minutes=admin_rag_service.AUTO_RETRY_COOLDOWN_MINUTES,
            )
            payload["cooldownUntil"] = cooldown_until.isoformat() if cooldown_until else None
            payload["maxAttempts"] = admin_rag_service.AUTO_RETRY_MAX_ATTEMPTS
            entries.append(AdminRagReindexQueueEntrySchema(**payload))
        except Exception:
            continue
    return AdminRagReindexQueueResponse(entries=entries, summary=summary_payload)


@router.post(
    "/reindex/queue/retry",
    response_model=AdminRagReindexRetryResponse,
    summary="실패한 재색인 작업을 재시작합니다.",
)
def retry_rag_reindex_from_queue(payload: AdminRagReindexRetryRequest) -> AdminRagReindexRetryResponse:
    queue_id = payload.queueId
    target_entry: Optional[Dict[str, object]] = None
    queue = admin_rag_service.load_retry_queue()
    for entry in queue:
        if str(entry.get("queueId")) == queue_id:
            target_entry = entry
            break
    if target_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="queue_entry_not_found")

    note = payload.note if payload.note is not None else target_entry.get("note")
    if payload.note is not None:
        admin_rag_service.update_retry_entry(queue_id, note=note)
        target_entry["note"] = note

    override_sources = _normalize_sources(payload.sources) if payload.sources else None
    if override_sources:
        sources = override_sources
    else:
        scope = str(target_entry.get("scope") or "")
        sources = admin_rag_service.split_scope_value(scope)

    response = _perform_reindex(
        actor=payload.actor,
        sources=sources,
        note=note,
        queue_id=queue_id,
        retry_entry=target_entry,
        retry_mode="manual",
    )
    return AdminRagReindexRetryResponse(queueId=queue_id, taskId=response.taskId, status=response.status)


@router.delete(
    "/reindex/queue/{queue_id}",
    response_model=AdminRagReindexRetryResponse,
    summary="재시도 큐에서 항목을 제거합니다.",
)
def remove_rag_reindex_queue_entry(queue_id: str) -> AdminRagReindexRetryResponse:
    if not admin_rag_service.remove_retry_entry(queue_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="queue_entry_not_found")
    return AdminRagReindexRetryResponse(queueId=queue_id, taskId=None, status="removed")


@router.get(
    "/audit/logs",
    summary="RAG 감사 로그를 다운로드합니다.",
    response_class=FileResponse,
)
def download_rag_audit_log() -> FileResponse:
    audit_path = (_AUDIT_DIR / "rag_audit.jsonl").resolve()
    if not audit_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit_log_not_found")
    return FileResponse(audit_path, media_type="application/json", filename="rag_audit.jsonl")
