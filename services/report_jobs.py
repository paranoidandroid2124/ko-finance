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

    raise RuntimeError("Daily brief generation is disabled.")


def run_daily_brief(*, target_date_iso: Optional[str], compile_pdf: bool, force: bool):
    """Execute the daily brief task synchronously."""

    raise RuntimeError("Daily brief generation is disabled.")


__all__ = ["enqueue_daily_brief", "run_daily_brief"]
