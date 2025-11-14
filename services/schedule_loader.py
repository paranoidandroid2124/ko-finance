"""Helpers for loading shared Celery beat schedules from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml
from celery.schedules import crontab

DEFAULT_SCHEDULE_FILE = Path("configs") / "schedules" / "ingest.yml"


def _cron_from_string(expr: str) -> crontab:
    """Convert a 5-field cron expression into a Celery ``crontab`` object."""
    fields = str(expr or "").split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression '{expr}'. Expected 5 fields.")
    minute, hour, day_of_month, month, day_of_week = fields
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month,
        day_of_week=day_of_week,
    )


def load_schedule_config(path: Optional[Path] = None) -> Tuple[Optional[str], Dict[str, Dict[str, Any]], Path]:
    """Return timezone + raw schedule entries from the YAML definition."""
    schedule_path = path or DEFAULT_SCHEDULE_FILE
    if not schedule_path.exists():
        return None, {}, schedule_path

    try:
        raw = yaml.safe_load(schedule_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - config parse guard
        raise RuntimeError(f"Failed to parse Celery schedule file: {schedule_path}") from exc

    entries: Dict[str, Dict[str, Any]] = {}
    for name, payload in (raw.get("entries") or {}).items():
        if not isinstance(payload, dict):
            continue
        task = payload.get("task")
        cron = payload.get("cron")
        if not task or not cron:
            continue
        entries[name] = {
            "task": str(task),
            "cron": str(cron),
            "args": list(payload.get("args") or []),
            "kwargs": dict(payload.get("kwargs") or {}),
            "options": dict(payload.get("options") or {}),
        }
    return raw.get("timezone"), entries, schedule_path


def as_celery_schedule(entries: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert raw YAML schedule entries into Celery beat schedule structures."""
    schedule: Dict[str, Dict[str, Any]] = {}
    for name, payload in entries.items():
        cron_expr = payload.get("cron")
        if not cron_expr:
            continue
        entry = {
            "task": payload["task"],
            "schedule": _cron_from_string(cron_expr),
            "args": payload.get("args", []),
            "kwargs": payload.get("kwargs", {}),
        }
        options = payload.get("options")
        if options:
            entry["options"] = options
        schedule[name] = entry
    return schedule


__all__ = ["DEFAULT_SCHEDULE_FILE", "as_celery_schedule", "load_schedule_config"]
