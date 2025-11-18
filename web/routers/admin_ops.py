"""Admin operations & scheduling endpoints wired to Celery and persisted config."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import uuid
from pathlib import Path as FilePath
from typing import Any, Dict, List, Mapping, Optional

from fastapi import HTTPException, Path, Query, status
from fastapi.responses import FileResponse

from schemas.api.admin import (
    AdminOpsAlertChannelCreateRequest,
    AdminOpsAlertChannelPreviewRequest,
    AdminOpsAlertChannelPreviewResponse,
    AdminOpsAlertChannelResponse,
    AdminOpsAlertChannelSchema,
    AdminOpsAlertChannelStatusUpdateRequest,
    AdminOpsAlertChannelUpdateRequest,
    AdminAuditLogEntrySchema,
    AdminAuditLogListResponse,
    AdminOpsApiKeyCollection,
    AdminOpsApiKeyResponse,
    AdminOpsApiKeySchema,
    AdminOpsApiKeyUpdateRequest,
    AdminOpsNewsPipelineResponse,
    AdminOpsNewsPipelineSchema,
    AdminOpsNewsPipelineUpdateRequest,
    AdminOpsRunHistoryResponse,
    AdminOpsRunRecordSchema,
    AdminOpsSampleMetadataRequest,
    AdminOpsSampleMetadataResponse,
    AdminOpsScheduleListResponse,
    AdminOpsScheduleSchema,
    AdminOpsTemplateListResponse,
    AdminOpsTemplateSchema,
    AdminOpsTriggerRequest,
    AdminOpsTriggerResponse,
    AdminOpsQuickActionRequest,
    AdminOpsQuickActionResponse,
    AdminAlertPresetUsageResponse,
)
from services import admin_ops_service, admin_ops_jobs
from services.admin_audit import append_audit_log
from services.alerts import summarize_preset_usage
from web.routers.admin_utils import create_admin_router
from web.routers.admin_rag import _perform_reindex

router = create_admin_router(
    prefix="/admin/ops",
    tags=["Admin Ops"],
)

_AUDIT_DIR = FilePath("uploads") / "admin"

_QUICK_ACTION_TASKS: Dict[str, Dict[str, object]] = {
    "seed-news": {"task": "m2.seed_news_feeds"},
    "aggregate-sentiment": {"task": "m2.aggregate_news"},
}


def _dispatch_celery_task(task_name: str, kwargs: Optional[Dict[str, object]] = None) -> str:
    return admin_ops_jobs.dispatch_task(task_name, kwargs)


def _human_interval(schedule_obj: object) -> str:
    if schedule_obj is None:
        return "unknown"
    for attr in ("human_readable", "__repr__", "__str__"):
        func = getattr(schedule_obj, attr, None)
        if callable(func):
            try:
                value = func() if attr != "__str__" else str(schedule_obj)
                if value:
                    return str(value)
            except Exception:
                continue
    return str(schedule_obj)


def _load_schedule(job_id: str) -> Optional[Dict[str, object]]:
    schedules = admin_ops_jobs.collect_schedules()
    return schedules.get(job_id)


def _build_schedule_list() -> List[AdminOpsScheduleSchema]:
    schedules = admin_ops_jobs.collect_schedules()
    items: List[AdminOpsScheduleSchema] = []
    for job_id, entry in schedules.items():
        task_name = entry.get("task")
        schedule_obj = entry.get("schedule")
        enabled = entry.get("enabled", True)
        status_value: str = "active" if enabled not in (False, "false", 0) else "paused"
        items.append(
            AdminOpsScheduleSchema(
                id=str(job_id),
                task=str(task_name or ""),
                interval=_human_interval(schedule_obj),
                status=status_value,
                nextRunAt=None,
            )
        )
    items.sort(key=lambda item: item.id)
    return items


def _news_pipeline_response(raw: Dict[str, object]) -> AdminOpsNewsPipelineResponse:
    pipeline = AdminOpsNewsPipelineSchema(
        rssFeeds=list(raw.get("rssFeeds") or []),
        sectorMappings={key: list(value) for key, value in (raw.get("sectorMappings") or {}).items()},
        sentiment=dict(raw.get("sentiment") or {}),
    )
    return AdminOpsNewsPipelineResponse(
        pipeline=pipeline,
        updatedAt=raw.get("updatedAt"),
        updatedBy=raw.get("updatedBy"),
    )


def _coerce_langfuse_config(value: object) -> AdminOpsLangfuseConfigSchema:
    payload: Dict[str, Any] = {}
    if isinstance(value, Mapping):
        payload = dict(value)
    default_env = payload.get("defaultEnvironment")
    if not isinstance(default_env, str) or not default_env.strip():
        payload["defaultEnvironment"] = "production"
    environments = payload.get("environments")
    if not isinstance(environments, list):
        payload["environments"] = []
    try:
        return AdminOpsLangfuseConfigSchema(**payload)
    except Exception:
        return AdminOpsLangfuseConfigSchema(defaultEnvironment="production", environments=[])


def _api_keys_response(raw: Dict[str, object]) -> AdminOpsApiKeyResponse:
    external = []
    for item in raw.get("externalApis", []):
        if isinstance(item, dict):
            try:
                external.append(AdminOpsApiKeySchema(**item))
            except Exception:
                continue
    langfuse = _coerce_langfuse_config(raw.get("langfuse"))
    secrets = AdminOpsApiKeyCollection(
        langfuse=langfuse,
        externalApis=external,
    )
    return AdminOpsApiKeyResponse(
        secrets=secrets,
        updatedAt=raw.get("updatedAt"),
        updatedBy=raw.get("updatedBy"),
    )


def _alert_channels_response(raw: Dict[str, object]) -> AdminOpsAlertChannelResponse:
    channels: List[AdminOpsAlertChannelSchema] = []
    for item in raw.get("channels", []):
        if isinstance(item, dict):
            try:
                channels.append(AdminOpsAlertChannelSchema(**item))
            except Exception:
                continue
    return AdminOpsAlertChannelResponse(
        channels=channels,
        updatedAt=raw.get("updatedAt"),
        updatedBy=raw.get("updatedBy"),
        note=raw.get("note"),
    )


@router.get(
    "/schedules",
    response_model=AdminOpsScheduleListResponse,
    summary="등록된 Celery 스케줄 목록을 조회합니다.",
)
def list_schedules() -> AdminOpsScheduleListResponse:
    return AdminOpsScheduleListResponse(jobs=_build_schedule_list())


@router.post(
    "/schedules/{job_id}/trigger",
    response_model=AdminOpsTriggerResponse,
    summary="특정 스케줄의 태스크를 수동으로 실행합니다.",
)
def trigger_schedule(
    payload: AdminOpsTriggerRequest,
    job_id: str = Path(..., description="트리거할 스케줄 ID."),
) -> AdminOpsTriggerResponse:
    entry = _load_schedule(job_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="schedule_not_found")

    task_id = f"{job_id}-run-{uuid.uuid4().hex[:8]}"
    admin_ops_service.append_run_history(
        task_id=task_id,
        job_id=job_id,
        task=str(entry.get("task") or ""),
        status="queued",
        actor=payload.actor,
        note=payload.note,
        started_at=None,
    )
    append_audit_log(
        filename="ops_audit.jsonl",
        actor=payload.actor,
        action="schedule_trigger",
        payload={"jobId": job_id, "taskId": task_id, "note": payload.note},
    )
    return AdminOpsTriggerResponse(jobId=job_id, taskId=task_id, status="queued")


@router.get(
    "/alert-presets/usage",
    response_model=AdminAlertPresetUsageResponse,
    summary="알림 프리셋 사용량 요약을 조회합니다.",
)
def read_alert_preset_usage(
    window_days: int = Query(default=14, ge=1, le=90, description="집계 기간(일)."),
) -> AdminAlertPresetUsageResponse:
    stats = summarize_preset_usage(window_days=window_days)
    return AdminAlertPresetUsageResponse(**stats)


@router.post(
    "/quick-actions/{action_id}",
    response_model=AdminOpsQuickActionResponse,
    summary="운영 퀵 액션을 실행합니다.",
)
def execute_quick_action(
    action_id: str,
    payload: AdminOpsQuickActionRequest,
) -> AdminOpsQuickActionResponse:
    action = action_id.strip()
    actor = payload.actor.strip()
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "quick_action.actor_required", "message": "actor 필드를 입력해 주세요."},
        )
    note = (payload.note or "").strip() or None

    if action in _QUICK_ACTION_TASKS:
        task_name = str(_QUICK_ACTION_TASKS[action].get("task"))
        kwargs = dict(_QUICK_ACTION_TASKS[action].get("kwargs") or {})
        try:
            task_id = _dispatch_celery_task(task_name, kwargs)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "quick_action.unavailable", "message": str(exc)},
            ) from exc

        admin_ops_service.append_run_history(
            task_id=task_id,
            job_id=f"quick-action.{action}",
            task=task_name,
            status="queued",
            actor=actor,
            note=note,
        )
        append_audit_log(
            filename="ops_audit.jsonl",
            actor=actor,
            action="quick_action_run",
            payload={"action": action, "task": task_name, "taskId": task_id, "note": note},
        )
        return AdminOpsQuickActionResponse(
            action=action,
            status="queued",
            taskId=task_id,
            message="작업이 큐에 등록됐어요.",
        )

    if action == "rebuild-rag":
        result = _perform_reindex(actor=actor, sources=[], note=note)
        append_audit_log(
            filename="ops_audit.jsonl",
            actor=actor,
            action="quick_action_run",
            payload={"action": action, "taskId": result.taskId, "status": result.status, "note": note},
        )
        return AdminOpsQuickActionResponse(
            action=action,
            status=result.status,
            taskId=result.taskId,
            message="RAG 재색인을 요청했어요.",
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "quick_action.not_found", "message": f"지원하지 않는 퀵 액션입니다: {action_id}"},
    )


@router.get(
    "/news-pipeline",
    response_model=AdminOpsNewsPipelineResponse,
    summary="뉴스 파이프라인 설정을 조회합니다.",
)
def read_news_pipeline() -> AdminOpsNewsPipelineResponse:
    payload = admin_ops_service.load_news_pipeline()
    return _news_pipeline_response(payload)


@router.put(
    "/news-pipeline",
    response_model=AdminOpsNewsPipelineResponse,
    summary="뉴스 파이프라인 설정을 업데이트합니다.",
)
def update_news_pipeline(payload: AdminOpsNewsPipelineUpdateRequest) -> AdminOpsNewsPipelineResponse:
    record = admin_ops_service.update_news_pipeline(
        rss_feeds=payload.rssFeeds,
        sector_mappings=payload.sectorMappings,
        sentiment=payload.sentiment,
        actor=payload.actor,
        note=payload.note,
    )
    if record.get("rssFeeds"):
        os.environ["NEWS_FEEDS"] = ",".join(record["rssFeeds"])
    return _news_pipeline_response(record)


@router.get(
    "/api-keys",
    response_model=AdminOpsApiKeyResponse,
    summary="운영 API 키/비밀 설정을 조회합니다.",
)
def read_api_keys() -> AdminOpsApiKeyResponse:
    payload = admin_ops_service.load_api_keys()
    return _api_keys_response(payload)


@router.put(
    "/api-keys",
    response_model=AdminOpsApiKeyResponse,
    summary="운영 API 키/비밀 설정을 업데이트합니다.",
)
def update_api_keys(payload: AdminOpsApiKeyUpdateRequest) -> AdminOpsApiKeyResponse:
    record = admin_ops_service.update_api_keys(
        langfuse=dict(payload.langfuse),
        external_apis=[item.model_dump() for item in payload.externalApis],
        actor=payload.actor,
        note=payload.note,
    )
    return _api_keys_response(record)


@router.post(
    "/api-keys/langfuse/rotate",
    response_model=AdminOpsApiKeyResponse,
    summary="Langfuse 토큰을 재발급합니다.",
)
def rotate_langfuse_api_keys(payload: AdminOpsTriggerRequest) -> AdminOpsApiKeyResponse:
    record = admin_ops_service.rotate_langfuse_keys(actor=payload.actor, note=payload.note)
    return _api_keys_response(record)


@router.get(
    "/alert-templates",
    response_model=AdminOpsTemplateListResponse,
    summary="알림 템플릿 갤러리를 조회합니다.",
)
def list_alert_templates() -> AdminOpsTemplateListResponse:
    templates = admin_ops_service.list_alert_templates()
    items = [AdminOpsTemplateSchema(**template) for template in templates]
    return AdminOpsTemplateListResponse(templates=items)


@router.post(
    "/alert-channels/sample-metadata",
    response_model=AdminOpsSampleMetadataResponse,
    summary="채널 유형에 맞는 샘플 메타데이터를 자동으로 생성합니다.",
)
def generate_alert_sample_metadata(payload: AdminOpsSampleMetadataRequest) -> AdminOpsSampleMetadataResponse:
    metadata = admin_ops_service.build_sample_metadata(
        channel_type=payload.channelType,
        template=payload.template,
    )
    return AdminOpsSampleMetadataResponse(metadata=metadata, generatedAt=datetime.now(timezone.utc).isoformat())


@router.get(
    "/alert-channels",
    response_model=AdminOpsAlertChannelResponse,
    summary="알림 채널 설정을 조회합니다.",
)
def read_alert_channels() -> AdminOpsAlertChannelResponse:
    payload = admin_ops_service.load_alert_channels()
    return _alert_channels_response(payload)


@router.post(
    "/alert-channels",
    response_model=AdminOpsAlertChannelResponse,
    summary="알림 채널을 추가합니다.",
    status_code=status.HTTP_201_CREATED,
)
def create_alert_channel(payload: AdminOpsAlertChannelCreateRequest) -> AdminOpsAlertChannelResponse:
    record = admin_ops_service.create_alert_channel(
        channel=payload.model_dump(exclude={"actor", "note"}),
        actor=payload.actor,
        note=payload.note,
    )
    return _alert_channels_response(record)


@router.put(
    "/alert-channels",
    response_model=AdminOpsAlertChannelResponse,
    summary="알림 채널 설정을 업데이트합니다.",
)
def update_alert_channels(payload: AdminOpsAlertChannelUpdateRequest) -> AdminOpsAlertChannelResponse:
    record = admin_ops_service.update_alert_channels(
        channels=[item.model_dump() for item in payload.channels],
        actor=payload.actor,
        note=payload.note,
    )
    return _alert_channels_response(record)


@router.patch(
    "/alert-channels/{key}/status",
    response_model=AdminOpsAlertChannelResponse,
    summary="알림 채널 활성화 상태를 변경합니다.",
)
def update_alert_channel_status(
    payload: AdminOpsAlertChannelStatusUpdateRequest,
    key: str = Path(..., description="변경할 채널 키."),
) -> AdminOpsAlertChannelResponse:
    try:
        record = admin_ops_service.update_channel_status(
            key=key,
            enabled=payload.enabled,
            actor=payload.actor,
            note=payload.note,
        )
    except ValueError as exc:  # pragma: no cover - defensive branch
        if str(exc) == "channel_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="channel_not_found") from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="channel_update_failed") from exc
    return _alert_channels_response(record)


@router.post(
    "/alert-channels/preview",
    response_model=AdminOpsAlertChannelPreviewResponse,
    summary="알림 채널 메시지 템플릿 미리보기를 생성합니다.",
)
def preview_alert_channel(payload: AdminOpsAlertChannelPreviewRequest) -> AdminOpsAlertChannelPreviewResponse:
    preview = admin_ops_service.build_channel_preview_payload(
        channel=payload.channel.model_dump(),
        sample_message=payload.sampleMessage,
        sample_metadata=payload.sampleMetadata,
        actor=payload.actor,
    )
    return AdminOpsAlertChannelPreviewResponse(**preview)


@router.get(
    "/audit/logs",
    response_model=AdminAuditLogListResponse,
    summary="감사 로그를 통합 조회합니다.",
)
def read_audit_logs(
    limit: int = Query(100, ge=1, le=1000, description="가져올 최대 로그 개수"),
    source: Optional[List[str]] = Query(None, description="필터링할 감사 파일 이름"),
    actor: Optional[str] = Query(None, description="필터링할 actor"),
    action: Optional[str] = Query(None, description="필터링할 action 코드"),
    search: Optional[str] = Query(None, alias="q", description="요약 검색 문자열"),
    since: Optional[str] = Query(None, description="ISO8601 시작 시각(포함)"),
    until: Optional[str] = Query(None, description="ISO8601 종료 시각(포함)"),
) -> AdminAuditLogListResponse:
    raw_records = admin_ops_service.list_audit_records(
        limit=min(limit + 1, 1000),
        sources=source,
        actor=actor,
        action=action,
        search=search,
        since=since,
        until=until,
    )
    has_more = len(raw_records) > limit
    if has_more:
        raw_records = raw_records[:limit]
    items = [AdminAuditLogEntrySchema(**record) for record in raw_records]
    next_cursor = raw_records[-1]["timestamp"] if has_more and raw_records else None
    return AdminAuditLogListResponse(items=items, hasMore=has_more, nextCursor=next_cursor)


@router.get(
    "/run-history",
    response_model=AdminOpsRunHistoryResponse,
    summary="최근 실행 기록을 조회합니다.",
)
def read_run_history() -> AdminOpsRunHistoryResponse:
    runs_raw = admin_ops_service.list_run_history(limit=50)
    runs: List[AdminOpsRunRecordSchema] = []
    for item in runs_raw:
        try:
            runs.append(AdminOpsRunRecordSchema(**item))
        except Exception:
            continue
    return AdminOpsRunHistoryResponse(runs=runs)


@router.get(
    "/audit/logs",
    summary="운영 감사 로그를 다운로드합니다.",
    response_class=FileResponse,
)
def download_ops_audit_log() -> FileResponse:
    audit_path = (_AUDIT_DIR / "ops_audit.jsonl").resolve()
    if not audit_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit_log_not_found")
    return FileResponse(audit_path, media_type="application/json", filename="ops_audit.jsonl")
