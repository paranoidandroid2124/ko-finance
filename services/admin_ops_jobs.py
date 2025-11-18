"""Celery control helpers for admin operations."""

from __future__ import annotations

import uuid
from typing import Dict, Optional

from core.logging import get_logger

try:  # pragma: no cover - optional dependency
    from parse.celery_app import app as celery_app  # type: ignore
except Exception:  # pragma: no cover
    celery_app = None

try:  # pragma: no cover
    from parse.worker import app as worker_app  # type: ignore
except Exception:  # pragma: no cover
    worker_app = None

logger = get_logger(__name__)


def _active_app():
    app = worker_app or celery_app
    if not app:
        raise RuntimeError("Celery worker가 활성화되어 있지 않습니다.")
    return app


def dispatch_task(task_name: str, kwargs: Optional[Dict[str, object]] = None) -> str:
    """Send a Celery task to either the worker app or the default app."""

    app = _active_app()
    async_result = app.send_task(task_name, kwargs=kwargs or {})
    task_id = getattr(async_result, "id", None)
    if not task_id:
        task_id = f"{task_name}-{uuid.uuid4().hex[:8]}"
    return task_id


def collect_schedules() -> Dict[str, Dict[str, object]]:
    """Return a merged dictionary of Celery beat schedules from all apps."""

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


def load_schedule(job_id: str) -> Optional[Dict[str, object]]:
    """Return a specific beat schedule entry by id."""

    return collect_schedules().get(job_id)


__all__ = ["dispatch_task", "collect_schedules", "load_schedule"]
