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
from services.plan_service import PlanContext
from web.deps import require_plan_feature

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # fallback path base


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
    return DailyBriefListResponse(items=[])


@router.post("/daily-brief/generate", response_model=DailyBriefGenerateResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_daily_brief(
    payload: DailyBriefGenerateRequest,
    _: PlanContext = Depends(require_plan_feature("search.export")),
) -> DailyBriefGenerateResponse:
    ref_date = payload.referenceDate or datetime.now(_KST).date()
    return DailyBriefGenerateResponse(
        status="disabled",
        referenceDate=ref_date,
        taskId=None,
        artifactPath=None,
        artifactUrl=None,
    )


@router.get("/daily-brief/{reference_date}/pdf")
def download_daily_brief_pdf(reference_date: str, _: PlanContext = Depends(require_plan_feature("evidence.inline_pdf"))):
    try:
        parsed_date = datetime.fromisoformat(reference_date).date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use ISO YYYY-MM-DD.")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily brief is disabled.")


@router.get("/daily-brief/{reference_date}/tex")
def download_daily_brief_tex(reference_date: str, _: PlanContext = Depends(require_plan_feature("evidence.inline_pdf"))):
    try:
        parsed_date = datetime.fromisoformat(reference_date).date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use ISO YYYY-MM-DD.")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Daily brief is disabled.")
