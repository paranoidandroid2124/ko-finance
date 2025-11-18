"""Celery helpers for report/daily brief workflows."""

from __future__ import annotations

from typing import Optional

from core.logging import get_logger

try:  # pragma: no cover - optional task import
    from parse.tasks import generate_daily_brief
except Exception:  # pragma: no cover
    generate_daily_brief = None  # type: ignore[assignment]

logger = get_logger(__name__)


def enqueue_daily_brief(*, target_date_iso: Optional[str], compile_pdf: bool, force: bool) -> str:
    """Schedule the asynchronous daily brief generation task."""

    if not generate_daily_brief:
        raise RuntimeError("generate_daily_brief task is unavailable; Celery worker not configured.")

    task = generate_daily_brief.apply_async(
        kwargs={
            "target_date_iso": target_date_iso,
            "compile_pdf": compile_pdf,
            "force": force,
        }
    )
    return str(getattr(task, "id", "")) or ""


def run_daily_brief(*, target_date_iso: Optional[str], compile_pdf: bool, force: bool):
    """Execute the daily brief task synchronously."""

    if not generate_daily_brief:
        raise RuntimeError("generate_daily_brief task is unavailable; Celery worker not configured.")
    return generate_daily_brief(
        target_date_iso=target_date_iso,
        compile_pdf=compile_pdf,
        force=force,
    )


__all__ = ["enqueue_daily_brief", "run_daily_brief"]
