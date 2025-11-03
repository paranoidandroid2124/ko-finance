"""Admin operations & scheduling endpoints wired to Celery and persisted config."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import uuid
from pathlib import Path as FilePath
from typing import Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
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
    PromptChannel,
)
from services import admin_ops_service
from services.admin_audit import append_audit_log
from web.deps_admin import require_admin_session

try:
    from parse.celery_app import app as celery_app  # type: ignore
except Exception:  # pragma: no cover - optional import during tests
    celery_app = None

try:
    from parse.worker import app as worker_app  # type: ignore
except Exception:  # pragma: no cover
    worker_app = None

router = APIRouter(
    prefix="/admin/ops",
    tags=["Admin Ops"],
    dependencies=[Depends(require_admin_session)],
)

_AUDIT_DIR = FilePath("uploads") / "admin"


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


def _collect_celery_schedules() -> Dict[str, Dict[str, object]]:
    merged: Dict[str, Dict[str, object]] = {}
    for app in (celery_app, worker_app):
        if not app:
            continue
        try:
            schedule_map = app.conf.beat_schedule  # type: ignore[attr-defined]
        except AttributeError:
            schedule_map = None
        if isinstance(schedule_map, dict):
            merged.update(schedule_map)
    return merged


def _load_schedule(job_id: str) -> Optional[Dict[str, object]]:
    schedules = _collect_celery_schedules()
    return schedules.get(job_id)


def _build_schedule_list() -> List[AdminOpsScheduleSchema]:
    schedules = _collect_celery_schedules()
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


def _api_keys_response(raw: Dict[str, object]) -> AdminOpsApiKeyResponse:
    external = []
    for item in raw.get("externalApis", []):
        if isinstance(item, dict):
            try:
                external.append(AdminOpsApiKeySchema(**item))
            except Exception:
                continue
    secrets = AdminOpsApiKeyCollection(
        langfuse=dict(raw.get("langfuse") or {}),
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
