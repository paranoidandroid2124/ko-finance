from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from core.logging import get_logger
from schemas.api.reports import (
    DailyBriefGenerateRequest,
    DailyBriefGenerateResponse,
    DailyBriefListResponse,
    DailyBriefRun,
    FileArtifact,
)
from services import storage_service, report_jobs
from services.daily_brief_service import (
    DAILY_BRIEF_OUTPUT_ROOT,
    list_daily_brief_runs,
    resolve_daily_brief_paths,
)
from services.plan_service import PlanContext
from web.deps import require_plan_feature

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_REPO_ROOT = DAILY_BRIEF_OUTPUT_ROOT.parent.parent


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
        task_id = report_jobs.enqueue_daily_brief(
            target_date_iso=reference_date_iso,
            compile_pdf=payload.compilePdf,
            force=payload.force,
        )
        ref_date = payload.referenceDate or datetime.now(_KST).date()
        return DailyBriefGenerateResponse(
            status="queued",
            referenceDate=ref_date,
            taskId=task_id,
        )

    result = report_jobs.run_daily_brief(
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
