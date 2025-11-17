"""JSON-backed helpers for managing watchlist digest schedules."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

STORE_PATH = Path("uploads") / "watchlist" / "digest_schedules.json"
_LOCK = threading.RLock()
DEFAULT_TIMEZONE = "Asia/Seoul"


def _ensure_store_dir() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_store() -> Dict[str, Dict[str, Any]]:
    if not STORE_PATH.exists():
        return {}
    try:
        raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _save_store(store: Dict[str, Dict[str, Any]]) -> None:
    _ensure_store_dir()
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_time_of_day(value: str) -> Tuple[int, int]:
    text = (value or "").strip()
    if len(text) != 5 or text[2] != ":":
        raise ValueError("timeOfDay must be formatted as HH:MM")
    hour_part, minute_part = text.split(":")
    hour = int(hour_part)
    minute = int(minute_part)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("timeOfDay must be within 00:00~23:59")
    return hour, minute


def _normalize_timezone(value: Optional[str]) -> str:
    tz = (value or DEFAULT_TIMEZONE).strip()
    try:
        ZoneInfo(tz)
    except Exception as exc:
        raise ValueError(f"Unknown timezone '{tz}'") from exc
    return tz


def _owner_matches(entry: Mapping[str, Any], filters: Mapping[str, Optional[uuid.UUID]]) -> bool:
    org_filter = filters.get("org_id")
    user_filter = filters.get("user_id")
    entry_org = entry.get("org_id")
    entry_user = entry.get("user_id")
    if org_filter:
        return entry_org == str(org_filter)
    if user_filter:
        return entry_user == str(user_filter)
    # default: only schedules without explicit owner
    return not entry_org and not entry_user


def _compute_next_run(
    schedule: Mapping[str, Any],
    *,
    from_time: Optional[datetime] = None,
) -> datetime:
    tz = ZoneInfo(schedule.get("timezone") or DEFAULT_TIMEZONE)
    hour, minute = _parse_time_of_day(schedule.get("time_of_day") or "09:00")
    base = (from_time or datetime.now(timezone.utc)).astimezone(tz)
    candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= base:
        candidate += timedelta(days=1)
    while schedule.get("weekdays_only") and candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def list_schedules(owner_filters: Mapping[str, Optional[uuid.UUID]]) -> List[Dict[str, Any]]:
    with _LOCK:
        store = _load_store()
        rows = [
            dict(value)
            for value in store.values()
            if _owner_matches(value, owner_filters)
        ]
    return rows


def load_schedule(schedule_id: uuid.UUID, owner_filters: Mapping[str, Optional[uuid.UUID]]) -> Optional[Dict[str, Any]]:
    with _LOCK:
        store = _load_store()
        entry = store.get(str(schedule_id))
        if entry and _owner_matches(entry, owner_filters):
            return dict(entry)
    return None


def _validate_targets(slack_targets: Sequence[str], email_targets: Sequence[str]) -> None:
    if not any(target.strip() for target in slack_targets) and not any(
        target.strip() for target in email_targets
    ):
        raise ValueError("최소 한 개 이상의 Slack 또는 이메일 대상이 필요합니다.")


def create_schedule(
    *,
    label: str,
    owner_filters: Mapping[str, Optional[uuid.UUID]],
    window_minutes: int,
    limit: int,
    time_of_day: str,
    timezone_name: Optional[str],
    weekdays_only: bool,
    slack_targets: Sequence[str],
    email_targets: Sequence[str],
    enabled: bool,
    actor: Optional[str],
) -> Dict[str, Any]:
    _validate_targets(slack_targets, email_targets)
    schedule_id = uuid.uuid4()
    timezone_value = _normalize_timezone(timezone_name)
    storage_entry: Dict[str, Any] = {
        "id": str(schedule_id),
        "label": label.strip() or "Digest Schedule",
        "org_id": str(owner_filters.get("org_id")) if owner_filters.get("org_id") else None,
        "user_id": str(owner_filters.get("user_id")) if owner_filters.get("user_id") else None,
        "window_minutes": int(window_minutes),
        "limit": int(limit),
        "time_of_day": time_of_day,
        "timezone": timezone_value,
        "weekdays_only": bool(weekdays_only),
        "slack_targets": [target.strip() for target in slack_targets if target.strip()],
        "email_targets": [target.strip() for target in email_targets if target.strip()],
        "enabled": bool(enabled),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": actor or None,
        "updated_by": actor or None,
        "last_dispatched_at": None,
        "last_status": None,
        "last_error": None,
    }
    next_run = _compute_next_run(storage_entry)
    storage_entry["next_run_at"] = next_run.isoformat()
    with _LOCK:
        store = dict(_load_store())
        store[str(schedule_id)] = storage_entry
        _save_store(store)
    return dict(storage_entry)


def update_schedule(
    schedule_id: uuid.UUID,
    owner_filters: Mapping[str, Optional[uuid.UUID]],
    *,
    label: Optional[str] = None,
    window_minutes: Optional[int] = None,
    limit: Optional[int] = None,
    time_of_day: Optional[str] = None,
    timezone_name: Optional[str] = None,
    weekdays_only: Optional[bool] = None,
    slack_targets: Optional[Sequence[str]] = None,
    email_targets: Optional[Sequence[str]] = None,
    enabled: Optional[bool] = None,
    actor: Optional[str] = None,
) -> Dict[str, Any]:
    with _LOCK:
        store = dict(_load_store())
        entry = store.get(str(schedule_id))
        if not entry or not _owner_matches(entry, owner_filters):
            raise KeyError("schedule_not_found")
        if slack_targets is not None or email_targets is not None:
            _validate_targets(slack_targets or entry.get("slack_targets") or [], email_targets or entry.get("email_targets") or [])
        if label is not None:
            entry["label"] = label.strip() or entry["label"]
        if window_minutes is not None:
            entry["window_minutes"] = int(window_minutes)
        if limit is not None:
            entry["limit"] = int(limit)
        if time_of_day is not None:
            _parse_time_of_day(time_of_day)
            entry["time_of_day"] = time_of_day
        if timezone_name is not None:
            entry["timezone"] = _normalize_timezone(timezone_name)
        if weekdays_only is not None:
            entry["weekdays_only"] = bool(weekdays_only)
        if slack_targets is not None:
            entry["slack_targets"] = [target.strip() for target in slack_targets if target.strip()]
        if email_targets is not None:
            entry["email_targets"] = [target.strip() for target in email_targets if target.strip()]
        if enabled is not None:
            entry["enabled"] = bool(enabled)
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        entry["updated_by"] = actor or entry.get("updated_by")
        entry["next_run_at"] = _compute_next_run(entry).isoformat()
        store[str(schedule_id)] = entry
        _save_store(store)
    return dict(entry)


def delete_schedule(schedule_id: uuid.UUID, owner_filters: Mapping[str, Optional[uuid.UUID]]) -> None:
    with _LOCK:
        store = dict(_load_store())
        entry = store.get(str(schedule_id))
        if not entry or not _owner_matches(entry, owner_filters):
            raise KeyError("schedule_not_found")
        store.pop(str(schedule_id), None)
        _save_store(store)


def list_due_schedules(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    current = (now or datetime.now(timezone.utc))
    with _LOCK:
        store = _load_store()
        due = []
        for entry in store.values():
            if not entry.get("enabled"):
                continue
            next_run = entry.get("next_run_at")
            if not next_run:
                continue
            try:
                next_dt = datetime.fromisoformat(next_run)
            except ValueError:
                continue
            if next_dt <= current:
                due.append(dict(entry))
    return due


def mark_dispatched(
    schedule_id: uuid.UUID,
    *,
    dispatched_at: datetime,
    next_run: Optional[datetime],
    status: str,
    last_error: Optional[str] = None,
) -> None:
    with _LOCK:
        store = dict(_load_store())
        entry = store.get(str(schedule_id))
        if not entry:
            return
        entry["last_dispatched_at"] = dispatched_at.isoformat()
        entry["last_status"] = status
        entry["last_error"] = last_error
        if next_run:
            entry["next_run_at"] = next_run.isoformat()
        else:
            entry["next_run_at"] = _compute_next_run(entry, from_time=dispatched_at + timedelta(minutes=1)).isoformat()
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        store[str(schedule_id)] = entry
        _save_store(store)


__all__ = [
    "create_schedule",
    "update_schedule",
    "delete_schedule",
    "list_schedules",
    "load_schedule",
    "list_due_schedules",
    "mark_dispatched",
]
