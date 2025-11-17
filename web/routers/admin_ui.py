"""Admin UI & UX configuration endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from schemas.api.admin import (
    AdminUiUxSettingsResponse,
    AdminUiUxSettingsSchema,
    AdminUiUxSettingsUpdateRequest,
)
from services import admin_ui_service
from web.routers.admin_utils import create_admin_router

router = create_admin_router(
    prefix="/admin/ui",
    tags=["Admin UI"],
)

_AUDIT_DIR = Path("uploads") / "admin"


def _to_response(payload: Dict[str, object]) -> AdminUiUxSettingsResponse:
    settings = {
        "theme": payload.get("theme") or {},
        "defaults": payload.get("defaults") or {},
        "copy": payload.get("copy") or {},
        "banner": payload.get("banner") or {},
    }
    meta = {
        "updatedAt": payload.get("updatedAt"),
        "updatedBy": payload.get("updatedBy"),
    }
    return AdminUiUxSettingsResponse(
        settings=AdminUiUxSettingsSchema(**settings),
        **meta,
    )


@router.get(
    "/settings",
    response_model=AdminUiUxSettingsResponse,
    summary="현재 UI·UX 설정을 조회합니다.",
)
def read_ui_settings() -> AdminUiUxSettingsResponse:
    payload = admin_ui_service.load_ui_settings()
    return _to_response(payload)


@router.put(
    "/settings",
    response_model=AdminUiUxSettingsResponse,
    summary="UI·UX 설정을 업데이트합니다.",
)
def update_ui_settings(payload: AdminUiUxSettingsUpdateRequest) -> AdminUiUxSettingsResponse:
    record = admin_ui_service.update_ui_settings(
        settings=payload.settings.model_dump(),
        actor=payload.actor,
        note=payload.note,
    )
    return _to_response(record)


@router.get(
    "/audit/logs",
    summary="UI·UX 감사 로그를 다운로드합니다.",
    response_class=FileResponse,
)
def download_ui_audit_log() -> FileResponse:
    audit_path = (_AUDIT_DIR / "ui_audit.jsonl").resolve()
    if not audit_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit_log_not_found")
    return FileResponse(audit_path, media_type="application/json", filename="ui_audit.jsonl")


__all__ = ["router"]
