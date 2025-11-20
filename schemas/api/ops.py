from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CeleryScheduleEntry(BaseModel):
    task: str
    cron: str
    args: List[Any] = Field(default_factory=list)
    kwargs: Dict[str, Any] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)


class CeleryScheduleResponse(BaseModel):
    timezone: Optional[str]
    path: Optional[str]
    entries: Dict[str, CeleryScheduleEntry]
