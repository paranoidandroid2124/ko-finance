"""Persistence helpers for administrator-managed RAG configuration."""

from __future__ import annotations

import difflib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.env import env_int
from core.logging import get_logger
from database import SessionLocal
from models.evidence import EvidenceSnapshot
from services.admin_audit import append_audit_log
from services.admin_shared import (
    ADMIN_BASE_DIR,
    ensure_admin_dir,
    ensure_parent_dir,
    now_iso,
    parse_iso_datetime,
)

logger = get_logger(__name__)

_ADMIN_DIR = ADMIN_BASE_DIR
_RAG_CONFIG_PATH = _ADMIN_DIR / "rag_config.json"
_RAG_HISTORY_PATH = _ADMIN_DIR / "rag_reindex.jsonl"
_RAG_RETRY_QUEUE_PATH = _ADMIN_DIR / "rag_reindex_retry.json"

AUTO_RETRY_MAX_ATTEMPTS = env_int("ADMIN_RAG_AUTO_RETRY_MAX_ATTEMPTS", default=3)
AUTO_RETRY_COOLDOWN_MINUTES = env_int("ADMIN_RAG_AUTO_RETRY_COOLDOWN_MINUTES", default=30)
_EVIDENCE_DIFF_SAMPLE_LIMIT = env_int("ADMIN_RAG_EVIDENCE_DIFF_SAMPLE_LIMIT", 20, minimum=0)

_DEFAULT_RAG_CONFIG: Dict[str, object] = {
    "sources": [
        {"key": "filings", "name": "공시/재무제표", "enabled": True},
        {"key": "news", "name": "뉴스&섹터", "enabled": True},
        {"key": "patents", "name": "특허 데이터", "enabled": False},
    ],
    "filters": [],
    "similarityThreshold": 0.62,
    "rerankModel": "bge-reranker-large",
    "updatedAt": None,
    "updatedBy": None,
}


def load_rag_config() -> Dict[str, object]:
    if _RAG_CONFIG_PATH.exists():
        try:
            payload = json.loads(_RAG_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as exc:  # pragma: no cover
            logger.warning("Failed to parse RAG config store: %s", exc)
    return dict(_DEFAULT_RAG_CONFIG)


def save_rag_config(config: Dict[str, object]) -> None:
    ensure_parent_dir(_RAG_CONFIG_PATH, logger)
    try:
        _RAG_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write RAG config: {exc}") from exc


def update_rag_config(
    *,
    sources: List[Dict[str, object]],
    filters: Iterable[Dict[str, object]],
    similarity_threshold: float,
    rerank_model: Optional[str],
    actor: str,
    note: Optional[str],
) -> Dict[str, object]:
    payload = {
        "sources": list(sources),
        "filters": list(filters),
        "similarityThreshold": similarity_threshold,
        "rerankModel": rerank_model,
        "updatedAt": now_iso(),
        "updatedBy": actor,
        "note": note,
    }
    save_rag_config(payload)
    append_audit_log(
        filename="rag_audit.jsonl",
        actor=actor,
        action="rag_config_update",
        payload={"note": note, "enabled_sources": [s["key"] for s in sources if s.get("enabled")]},
    )
    return payload


def _read_json_file(path: Path, *, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive fallback
        logger.warning("Failed to parse JSON file %s: %s", path, exc)
        return default
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to read JSON file %s: %s", path, exc)
        return default


def _write_json_file(path: Path, payload: object) -> None:
    ensure_parent_dir(path, logger)
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write JSON file {path}: {exc}") from exc


def append_reindex_history(
    *,
    task_id: str,
    actor: str,
    scope: str,
    status: str,
    note: Optional[str],
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    duration_ms: Optional[int] = None,
    error_code: Optional[str] = None,
    langfuse_trace_url: Optional[str] = None,
    langfuse_trace_id: Optional[str] = None,
    langfuse_span_id: Optional[str] = None,
    queue_id: Optional[str] = None,
    retry_mode: Optional[str] = None,
    rag_mode: Optional[str] = None,
    scope_detail: Optional[Iterable[str]] = None,
    evidence_diff: Optional[Dict[str, Any]] = None,
) -> None:
    ensure_parent_dir(_RAG_HISTORY_PATH, logger)
    record = {
        "taskId": task_id,
        "actor": actor,
        "scope": scope,
        "status": status,
        "note": note,
        "timestamp": now_iso(),
        "startedAt": started_at,
        "finishedAt": finished_at,
        "durationMs": duration_ms,
        "errorCode": error_code,
        "langfuseTraceUrl": langfuse_trace_url,
        "langfuseTraceId": langfuse_trace_id,
        "langfuseSpanId": langfuse_span_id,
        "queueId": queue_id,
    }
    if evidence_diff:
        record["evidenceDiff"] = evidence_diff
    if retry_mode:
        record["retryMode"] = retry_mode
    if rag_mode:
        record["ragMode"] = rag_mode
    if scope_detail is not None:
        record["scopeDetail"] = list(scope_detail)
    try:
        with _RAG_HISTORY_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to append RAG history: %s", exc)


def list_reindex_history(limit: int = 50) -> List[Dict[str, object]]:
    if not _RAG_HISTORY_PATH.exists():
        return []
    try:
        lines = _RAG_HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to read RAG history: %s", exc)
        return []

    entries: List[Dict[str, object]] = []
    for line in reversed(lines[-limit:]):
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                entries.append(parsed)
        except json.JSONDecodeError:
            continue
    return entries


def load_retry_queue() -> List[Dict[str, object]]:
    payload = _read_json_file(_RAG_RETRY_QUEUE_PATH, default=[])
    if not isinstance(payload, list):
        return []
    entries: List[Dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            entries.append(item)
    entries.sort(
        key=lambda entry: entry.get("updatedAt") or entry.get("createdAt") or "",
        reverse=True,
    )
    return entries


def collect_due_retry_entries(
    *,
    max_attempts: int,
    cooldown_minutes: int,
    now: Optional[datetime] = None,
) -> List[Dict[str, object]]:
    if max_attempts <= 0:
        return []
    current_time = now or datetime.now(timezone.utc)
    cooldown_delta = timedelta(minutes=max(cooldown_minutes, 0))
    due_entries: List[Dict[str, object]] = []
    for entry in load_retry_queue():
        status = str(entry.get("status") or "").lower()
        if status not in {"queued", "failed"}:
            continue
        attempts = int(entry.get("attempts") or 0)
        if attempts >= max_attempts:
            continue
        last_attempt_at = parse_iso_datetime(entry.get("lastAttemptAt"))
        if last_attempt_at is None:
            due_entries.append(entry)
            continue
        if current_time - last_attempt_at >= cooldown_delta:
            due_entries.append(entry)
    return due_entries


def compute_next_retry_time(
    entry: Dict[str, object],
    *,
    cooldown_minutes: int,
) -> Optional[datetime]:
    last_attempt_at = parse_iso_datetime(entry.get("lastAttemptAt"))
    if last_attempt_at is None:
        return None
    return last_attempt_at + timedelta(minutes=max(cooldown_minutes, 0))


def split_scope_value(scope: str) -> List[str]:
    values: List[str] = []
    seen: set[str] = set()
    for raw in scope.split(","):
        text = raw.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _build_empty_evidence_diff() -> Dict[str, Any]:
    return {
        "totalChanges": 0,
        "created": 0,
        "updated": 0,
        "removed": 0,
        "samples": [],
    }


def _normalize_scope_filter(scope_detail: Optional[Iterable[str]]) -> Tuple[bool, set[str]]:
    if not scope_detail:
        return False, set()
    normalized = {str(item).strip().lower() for item in scope_detail if str(item).strip()}
    if "all" in normalized:
        return False, set()
    return True, normalized


def build_line_diff(before: Optional[str], after: Optional[str]) -> List[str]:
    before_lines = (before or "").splitlines()
    after_lines = (after or "").splitlines()
    diff = difflib.ndiff(before_lines, after_lines)
    lines: List[str] = []
    for entry in diff:
        if entry.startswith("?"):
            continue
        if entry.startswith("  "):
            lines.append(f"  {entry[2:]}")
        elif entry.startswith("+ "):
            lines.append(f"+ {entry[2:]}")
        elif entry.startswith("- "):
            lines.append(f"- {entry[2:]}")
        else:
            lines.append(entry)
        if len(lines) >= 40:
            break
    return lines


def extract_text_fields(payload: Mapping[str, Any]) -> Dict[str, str]:
    text_fields: Dict[str, str] = {}
    preferred_keys = ("quote", "content", "summary", "title", "body")
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            text_fields[key] = value
    if not text_fields:
        for key, value in payload.items():
            if isinstance(value, str) and value.strip():
                text_fields[str(key)] = value
                if len(text_fields) >= 3:
                    break
    return text_fields


def collect_evidence_diff(
    *,
    started_at: datetime,
    finished_at: Optional[datetime],
    scope_detail: Optional[Iterable[str]],
) -> Dict[str, Any]:
    summary = _build_empty_evidence_diff()

    try:
        session: Session = SessionLocal()
    except Exception as exc:  # pragma: no cover - database bootstrap guard
        logger.debug("Evidence diff session unavailable: %s", exc, exc_info=True)
        return summary

    apply_filter, scope_filter = _normalize_scope_filter(scope_detail)

    try:
        stmt = (
            select(EvidenceSnapshot)
            .where(EvidenceSnapshot.updated_at >= started_at)
            .order_by(EvidenceSnapshot.updated_at.desc())
        )
        if finished_at is not None:
            stmt = stmt.where(EvidenceSnapshot.updated_at <= finished_at)

        rows = session.execute(stmt).scalars().all()
    except Exception as exc:  # pragma: no cover - database errors transformed to empty diff
        logger.debug("Evidence diff query failed: %s", exc, exc_info=True)
        session.close()
        return summary

    samples: List[Dict[str, Any]] = []
    seen_samples: set[str] = set()
    snapshot_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for snapshot in rows:
        payload = snapshot.payload or {}
        cache_key = (str(snapshot.urn_id or ""), str(snapshot.snapshot_hash or ""))
        snapshot_cache[cache_key] = payload

        source_value = str(payload.get("source") or payload.get("source_name") or "").strip().lower()
        if apply_filter and source_value not in scope_filter:
            continue

        diff_type = str(snapshot.diff_type or "").lower()
        previous_payload: Dict[str, Any] = {}
        if snapshot.previous_snapshot_hash:
            previous_key = (str(snapshot.urn_id or ""), str(snapshot.previous_snapshot_hash))
            previous_payload = snapshot_cache.get(previous_key, {})
            if not previous_payload:
                try:
                    previous_snapshot = session.get(EvidenceSnapshot, previous_key)
                except Exception:
                    previous_snapshot = None
                if previous_snapshot is not None:
                    previous_payload = previous_snapshot.payload or {}
                    snapshot_cache[previous_key] = previous_payload

        visible_payload = payload
        if diff_type == "created":
            summary["created"] += 1
        elif diff_type == "updated":
            summary["updated"] += 1
        elif diff_type == "removed":
            summary["removed"] += 1
            if previous_payload:
                visible_payload = previous_payload
        else:
            continue

        summary["totalChanges"] = summary["created"] + summary["updated"] + summary["removed"]

        if len(samples) >= _EVIDENCE_DIFF_SAMPLE_LIMIT:
            continue

        urn_id = str(snapshot.urn_id or "")
        if urn_id and urn_id in seen_samples:
            continue
        if urn_id:
            seen_samples.add(urn_id)

        quote_text = visible_payload.get("quote") or visible_payload.get("content")
        if isinstance(quote_text, str) and len(quote_text) > 280:
            quote_text = f"{quote_text[:277]}..."

        text_before = extract_text_fields(previous_payload) if previous_payload else {}
        text_after = extract_text_fields(payload) if diff_type != "removed" else {}
        diff_changes: List[Dict[str, Any]] = []
        field_keys = set(text_before.keys()) | set(text_after.keys())
        for field in field_keys:
            before_value = text_before.get(field, "")
            after_value = text_after.get(field, "")
            if diff_type == "removed":
                after_value = ""
            if diff_type == "created":
                before_value = ""
            if str(before_value).strip() == str(after_value).strip():
                continue
            diff_lines = build_line_diff(str(before_value or ""), str(after_value or ""))
            diff_changes.append(
                {
                    "field": field,
                    "before": before_value or None,
                    "after": after_value or None,
                    "lineDiff": diff_lines,
                }
            )

        sample_entry: Dict[str, Any] = {
            "urnId": urn_id or None,
            "diffType": diff_type,
            "source": visible_payload.get("source"),
            "section": visible_payload.get("section"),
            "quote": quote_text,
            "chunkId": visible_payload.get("chunk_id") or visible_payload.get("id"),
            "updatedAt": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
        }
        if diff_changes:
            sample_entry["changes"] = diff_changes

        samples.append(sample_entry)

    summary["samples"] = samples
    session.close()
    return summary


def summarize_reindex_history(records: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    items = list(records)
    total = len(items)
    if total == 0:
        return {
            "totalRuns": 0,
            "completed": 0,
            "failed": 0,
            "traced": 0,
            "missingTraces": 0,
            "averageDurationMs": None,
            "latestTraceUrls": [],
            "modeUsage": {},
            "lastRunAt": None,
        }

    completed = sum(1 for item in items if str(item.get("status") or "").lower() == "completed")
    failed = sum(1 for item in items if str(item.get("status") or "").lower() == "failed")
    traced_urls = [str(item.get("langfuseTraceUrl")) for item in items if item.get("langfuseTraceUrl")]
    traced = len(traced_urls)
    durations = [int(item.get("durationMs")) for item in items if isinstance(item.get("durationMs"), int)]
    average = int(sum(durations) / len(durations)) if durations else None

    mode_usage: Dict[str, int] = {}
    for item in items:
        mode = str(item.get("ragMode") or "unknown").lower()
        mode_usage[mode] = mode_usage.get(mode, 0) + 1

    latest_urls: List[str] = []
    for url in traced_urls:
        if url not in latest_urls:
            latest_urls.append(url)
        if len(latest_urls) >= 5:
            break

    timestamps = [item.get("timestamp") for item in items if item.get("timestamp")]
    last_run_at = max(timestamps) if timestamps else None

    return {
        "totalRuns": total,
        "completed": completed,
        "failed": failed,
        "traced": traced,
        "missingTraces": total - traced,
        "averageDurationMs": average,
        "latestTraceUrls": latest_urls,
        "modeUsage": mode_usage,
        "lastRunAt": last_run_at,
    }


def summarize_retry_queue(entries: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    items = list(entries)
    total = len(items)
    if total == 0:
        return {
            "totalEntries": 0,
            "ready": 0,
            "coolingDown": 0,
            "autoMode": 0,
            "manualMode": 0,
            "nextAutoRetryAt": None,
            "stalled": 0,
        }

    now = datetime.now(timezone.utc)
    ready = 0
    cooling = 0
    auto_mode = 0
    manual_mode = 0
    stalled = 0
    next_auto: Optional[datetime] = None

    for item in items:
        retry_mode = str(item.get("retryMode") or "auto").lower()
        if retry_mode == "auto":
            auto_mode += 1
        else:
            manual_mode += 1

        cooldown_raw = item.get("cooldownUntil")
        cooldown_at = parse_iso_datetime(cooldown_raw) if cooldown_raw else None
        max_attempts = item.get("maxAttempts") or AUTO_RETRY_MAX_ATTEMPTS
        attempts = item.get("attempts") or 0
        if isinstance(attempts, str) and attempts.isdigit():
            attempts = int(attempts)
        if isinstance(max_attempts, str) and max_attempts.isdigit():
            max_attempts = int(max_attempts)
        if attempts >= max_attempts:
            stalled += 1

        if cooldown_at and cooldown_at > now:
            cooling += 1
            if retry_mode == "auto" and (next_auto is None or cooldown_at < next_auto):
                next_auto = cooldown_at
        else:
            status = str(item.get("status") or "").lower()
            if status in {"queued", "retrying"}:
                ready += 1

    return {
        "totalEntries": total,
        "ready": ready,
        "coolingDown": cooling,
        "autoMode": auto_mode,
        "manualMode": manual_mode,
        "nextAutoRetryAt": next_auto.isoformat() if next_auto else None,
        "stalled": stalled,
    }
def save_retry_queue(entries: List[Dict[str, object]]) -> None:
    _write_json_file(_RAG_RETRY_QUEUE_PATH, entries)


def enqueue_retry_entry(
    *,
    original_task_id: str,
    scope: str,
    actor: str,
    note: Optional[str],
    error_code: Optional[str],
    langfuse_trace_url: Optional[str],
    langfuse_trace_id: Optional[str],
    langfuse_span_id: Optional[str],
    retry_mode: str = "auto",
) -> Dict[str, object]:
    queue = load_retry_queue()
    queue_id = uuid.uuid4().hex
    timestamp = now_iso()
    entry = {
        "queueId": queue_id,
        "originalTaskId": original_task_id,
        "scope": scope,
        "actor": actor,
        "note": note,
        "status": "queued",
        "attempts": 0,
        "lastError": error_code,
        "lastTaskId": None,
        "lastAttemptAt": None,
        "lastSuccessAt": None,
        "langfuseTraceUrl": langfuse_trace_url,
        "langfuseTraceId": langfuse_trace_id,
        "langfuseSpanId": langfuse_span_id,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "retryMode": retry_mode,
    }
    queue.insert(0, entry)
    save_retry_queue(queue)
    return entry


def update_retry_entry(queue_id: str, **changes: object) -> Optional[Dict[str, object]]:
    queue = load_retry_queue()
    updated_entry: Optional[Dict[str, object]] = None
    for item in queue:
        if str(item.get("queueId")) == queue_id:
            item.update(changes)
            item["updatedAt"] = now_iso()
            updated_entry = item
            break
    if updated_entry is not None:
        save_retry_queue(queue)
    return updated_entry


def remove_retry_entry(queue_id: str) -> bool:
    queue = load_retry_queue()
    filtered = [item for item in queue if str(item.get("queueId")) != queue_id]
    if len(filtered) == len(queue):
        return False
    save_retry_queue(filtered)
    return True


__all__ = [
    "append_reindex_history",
    "list_reindex_history",
    "load_retry_queue",
    "collect_due_retry_entries",
    "compute_next_retry_time",
    "split_scope_value",
    "collect_evidence_diff",
    "summarize_reindex_history",
    "summarize_retry_queue",
    "enqueue_retry_entry",
    "update_retry_entry",
    "remove_retry_entry",
    "load_rag_config",
    "save_rag_config",
    "update_rag_config",
    "AUTO_RETRY_MAX_ATTEMPTS",
    "AUTO_RETRY_COOLDOWN_MINUTES",
]
