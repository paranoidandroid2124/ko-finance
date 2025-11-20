from __future__ import annotations

from fastapi import APIRouter, Depends

from schemas.api.ops import CeleryScheduleEntry, CeleryScheduleResponse
from services.schedule_loader import load_schedule_config
from web.deps_ops import require_ops_access

router = APIRouter(prefix="/ops", tags=["Ops"], dependencies=[Depends(require_ops_access)])


@router.get("/celery/schedule", response_model=CeleryScheduleResponse)
def read_celery_schedule() -> CeleryScheduleResponse:
    timezone, entries, path = load_schedule_config()
    serialized = {name: CeleryScheduleEntry(**entry) for name, entry in entries.items()}
    return CeleryScheduleResponse(
        timezone=timezone,
        path=str(path),
        entries=serialized,
    )
