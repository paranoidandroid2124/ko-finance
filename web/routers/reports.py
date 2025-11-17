from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from parse.tasks import generate_daily_brief
from core.logging import get_logger
from schemas.api.reports import (
    DailyBriefGenerateRequest,
    DailyBriefGenerateResponse,
    DailyBriefListResponse,
    DailyBriefRun,
    DigestPreviewResponse,
    FileArtifact,
)
from services import storage_service, lightmem_gate, lightmem_rate_limiter, digest_snapshot_service
from services.lightmem_config import DIGEST_RATE_LIMIT_PER_MINUTE
from services.daily_brief_service import (
    DAILY_BRIEF_OUTPUT_ROOT,
    build_digest_preview,
    list_daily_brief_runs,
    resolve_daily_brief_paths,
)
from services.plan_service import PlanContext
from web.deps import require_plan_feature
from web.quota_guard import enforce_quota

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_REPO_ROOT = DAILY_BRIEF_OUTPUT_ROOT.parent.parent
_DIGEST_PREVIEW_RATE_LIMIT = DIGEST_RATE_LIMIT_PER_MINUTE
_RATE_LIMIT_SCOPE = "digest.preview"


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _make_artifact(payload: dict) -> FileArtifact:
    return FileArtifact(
        path=payload["path"],
        exists=payload["exists"],
        sizeBytes=payload.get("size_bytes"),
        downloadUrl=payload.get("download_url"),
        provider=payload.get("provider"),
    )


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format.")


@router.get("/digest/preview", response_model=DigestPreviewResponse)
def read_digest_preview(
    timeframe: str = Query(default="daily", description="daily 혹은 weekly"),
    reference_date: Optional[date] = Query(default=None, alias="referenceDate"),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("search.export")),
) -> DigestPreviewResponse:
    normalized = "weekly" if str(timeframe).lower() == "weekly" else "daily"
    user_id = _parse_uuid(x_user_id) if x_user_id else lightmem_gate.default_user_id()
    org_id = _parse_uuid(x_org_id)
    enforce_quota("watchlist.preview", plan=plan, user_id=user_id, org_id=org_id)
    owner_filters = {"user_id": user_id, "org_id": org_id}
    snapshot_payload = digest_snapshot_service.load_snapshot(
        db,
        timeframe=normalized,
        reference_date=reference_date,
        user_id=user_id,
        org_id=org_id,
    )
    if snapshot_payload:
        logger.info(
            "digest.preview.snapshot_hit",
            extra={
                "timeframe": normalized,
                "user_id": str(user_id) if user_id else None,
                "org_id": str(org_id) if org_id else None,
            },
        )
        return DigestPreviewResponse(**snapshot_payload)

    user_settings = lightmem_gate.load_user_settings(user_id)
    rate_identifier = str(org_id) if org_id else (str(user_id) if user_id else "global")
    rate_limit_result = lightmem_rate_limiter.check_limit(
        _RATE_LIMIT_SCOPE,
        rate_identifier,
        limit=_DIGEST_PREVIEW_RATE_LIMIT,
        window_seconds=60,
    )
    memory_allowed = lightmem_gate.digest_enabled(plan, user_settings)
    if not rate_limit_result.allowed:
        memory_allowed = False
        logger.warning(
            "digest.preview.rate_limited",
            extra={
                "timeframe": normalized,
                "user_id": str(user_id) if user_id else None,
                "org_id": str(org_id) if org_id else None,
                "rate_limit_remaining": rate_limit_result.remaining,
            },
        )
    preview_payload = build_digest_preview(
        reference_date=reference_date,
        session=db,
        timeframe=normalized,
        owner_filters=owner_filters,
        plan_memory_enabled=memory_allowed,
        tenant_id=str(org_id) if org_id else None,
        user_id_hint=str(user_id) if user_id else None,
    )
    try:
        digest_snapshot_service.upsert_snapshot(
            db,
            digest_date=reference_date or datetime.now(_KST).date(),
            timeframe=normalized,
            payload=preview_payload,
            user_id=user_id,
            org_id=org_id,
        )
        db.commit()
    except Exception as snapshot_exc:  # pragma: no cover - best effort persistence
        db.rollback()
        logger.warning("Digest preview snapshot upsert failed: %s", snapshot_exc, exc_info=True)
    logger.info(
        "digest.preview.served",
        extra={
            "timeframe": normalized,
            "news_count": len(preview_payload.get("news") or []),
            "watchlist_count": len(preview_payload.get("watchlist") or []),
            "has_sentiment": bool(preview_payload.get("sentiment")),
            "has_llm_overview": bool(preview_payload.get("llmOverview")),
            "has_personal_note": bool(preview_payload.get("llmPersonalNote")),
            "memory_enabled": memory_allowed,
            "user_id": str(user_id) if user_id else None,
            "org_id": str(org_id) if org_id else None,
            "rate_limited": not rate_limit_result.allowed,
            "rate_limit_remaining": rate_limit_result.remaining,
        },
    )
    return DigestPreviewResponse(**preview_payload)


@router.get("/daily-brief", response_model=DailyBriefListResponse)
def list_daily_brief_entries(
    limit: int = 10,
    db: Session = Depends(get_db),
    _: PlanContext = Depends(require_plan_feature("search.export")),
) -> DailyBriefListResponse:
    runs = list_daily_brief_runs(limit=limit, session=db)
    items = [
        DailyBriefRun(
            id=row["id"],
            referenceDate=row["reference_date"],
            channel=row["channel"],
            generatedAt=row["generated_at"],
            pdf=_make_artifact(row["pdf"]),
            tex=_make_artifact(row["tex"]),
        )
        for row in runs
    ]
    return DailyBriefListResponse(items=items)


@router.post("/daily-brief/generate", response_model=DailyBriefGenerateResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_daily_brief(
    payload: DailyBriefGenerateRequest,
    _: PlanContext = Depends(require_plan_feature("search.export")),
) -> DailyBriefGenerateResponse:
    reference_date_iso = payload.referenceDate.isoformat() if payload.referenceDate else None

    if payload.asyncMode:
        task = generate_daily_brief.apply_async(
            kwargs={
                "target_date_iso": reference_date_iso,
                "compile_pdf": payload.compilePdf,
                "force": payload.force,
            }
        )
        ref_date = payload.referenceDate or datetime.now(_KST).date()
        return DailyBriefGenerateResponse(
            status="queued",
            referenceDate=ref_date,
            taskId=task.id,
        )

    result = generate_daily_brief(
        target_date_iso=reference_date_iso,
        compile_pdf=payload.compilePdf,
        force=payload.force,
    )
    ref_date = payload.referenceDate or datetime.now(_KST).date()
    if result == "already_generated":
        return DailyBriefGenerateResponse(
            status="already_generated",
            referenceDate=ref_date,
        )

    artifact_path = Path(result)
    artifact_url = None
    paths = resolve_daily_brief_paths(ref_date)
    manifest_path = paths["manifest"]
    if manifest_path.is_file() and storage_service.is_enabled():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            pdf_entry = manifest.get("artifacts", {}).get("pdf", {}) if isinstance(manifest, dict) else {}
            object_name = pdf_entry.get("object_name") if isinstance(pdf_entry, dict) else None
            if object_name:
                artifact_url = storage_service.get_presigned_url(object_name)
        except Exception:  # pragma: no cover - defensive manifest guard
            artifact_url = None

    return DailyBriefGenerateResponse(
        status="completed",
        referenceDate=ref_date,
        artifactPath=_relative_path(artifact_path),
        artifactUrl=artifact_url,
    )


@router.get("/daily-brief/{reference_date}/pdf")
def download_daily_brief_pdf(reference_date: str, _: PlanContext = Depends(require_plan_feature("evidence.inline_pdf"))):
    try:
        parsed_date = datetime.fromisoformat(reference_date).date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use ISO YYYY-MM-DD.")

    paths = resolve_daily_brief_paths(parsed_date)
    pdf_path = paths["pdf"]
    if not pdf_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily brief PDF not found.")
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


@router.get("/daily-brief/{reference_date}/tex")
def download_daily_brief_tex(reference_date: str, _: PlanContext = Depends(require_plan_feature("evidence.inline_pdf"))):
    try:
        parsed_date = datetime.fromisoformat(reference_date).date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use ISO YYYY-MM-DD.")

    paths = resolve_daily_brief_paths(parsed_date)
    tex_path = paths["tex"]
    if not tex_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily brief TeX not found.")
    return FileResponse(tex_path, media_type="application/x-tex", filename=tex_path.name)
