"""Shared audit logging utilities for administrator actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.logging import get_logger

logger = get_logger(__name__)

_AUDIT_DIR = Path("uploads") / "admin"
_MASTER_AUDIT_FILE = _AUDIT_DIR / "audit_master.jsonl"



def _parse_filter_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:  # pragma: no cover - filter parsing best-effort
            logger.debug("Failed to parse audit filter datetime: %s", value)
            return None


def _ensure_audit_dir() -> None:
    try:
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to create admin audit directory: %s", exc)


def append_audit_log(
    *,
    filename: str,
    actor: str,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a structured audit entry to ``uploads/admin/<filename>`` in JSONL format.

    Parameters
    ----------
    filename:
        Target filename relative to ``uploads/admin`` (e.g. ``llm_audit.jsonl``).
    actor:
        Administrator identity performing the change.
    action:
        Short verb or action code describing the event.
    payload:
        Optional metadata payload for downstream inspection.
    """

    _ensure_audit_dir()
    entry_path = _AUDIT_DIR / filename
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "payload": payload or {},
        "source": filename,
    }

    try:
        with entry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
        with _MASTER_AUDIT_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to persist admin audit log (%s): %s", filename, exc)


def read_audit_logs(
    *,
    limit: int = 200,
    sources: Optional[Iterable[str]] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Read audit entries from the aggregated audit log with optional filtering.

    Parameters
    ----------
    limit:
        Maximum number of entries to return (newest first).
    sources:
        Optional iterable of source filenames to include.
    actor:
        Optional actor filter.
    action:
        Optional action filter.
    search:
        Optional substring to search across actor/action/source/payload.
    since / until:
        Optional ISO8601 timestamps for inclusive lower/upper bounds.
    """

    if not _MASTER_AUDIT_FILE.exists():
        return []

    allowed_sources = {source for source in (sources or []) if source}
    results: List[Dict[str, Any]] = []
    search_lower = search.lower() if search else None
    since_dt = _parse_filter_datetime(since)
    until_dt = _parse_filter_datetime(until)

    try:
        lines = _MASTER_AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to read audit master log: %s", exc)
        return []

    for raw_line in reversed(lines):
        if len(results) >= limit:
            break
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:  # pragma: no cover - defensive guard
            continue

        if allowed_sources and record.get("source") not in allowed_sources:
            continue
        if actor and record.get("actor") != actor:
            continue
        if action and record.get("action") != action:
            continue

        timestamp_raw = record.get("timestamp")
        timestamp_dt = _parse_filter_datetime(timestamp_raw) if timestamp_raw else None
        if since_dt and (timestamp_dt is None or timestamp_dt < since_dt):
            continue
        if until_dt and (timestamp_dt is None or timestamp_dt > until_dt):
            continue

        if search_lower:
            payload_str = ""
            try:
                payload_str = json.dumps(record.get("payload") or {}, ensure_ascii=False)
            except TypeError:  # pragma: no cover
                payload_str = str(record.get("payload"))
            haystacks = [
                record.get("actor"),
                record.get("action"),
                record.get("source"),
                payload_str,
            ]
            if not any(isinstance(value, str) and search_lower in value.lower() for value in haystacks):
                continue

        results.append(record)

    return results


__all__ = ["append_audit_log", "read_audit_logs"]
