"""Audit & trace log synchronisation helpers for BigQuery and GCS."""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Tuple

from core.env import env_int, env_str
from services import bigquery_service, storage_service

try:  # pragma: no cover - optional dependency
    from google.cloud import bigquery  # type: ignore
except ImportError:  # pragma: no cover
    bigquery = None  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG_PATH = REPO_ROOT / "uploads" / "admin" / "audit_master.jsonl"
REINDEX_LOG_PATH = REPO_ROOT / "uploads" / "admin" / "rag_reindex.jsonl"
STATE_DIR = REPO_ROOT / ".state"

AUDIT_DATASET = env_str("BIGQUERY_AUDIT_DATASET", "kfinance_audit").strip()
AUDIT_TABLE = env_str("BIGQUERY_AUDIT_TABLE", "admin_events").strip()
REINDEX_TABLE = env_str("BIGQUERY_REINDEX_TABLE", "reindex_runs").strip()
GCS_AUDIT_PREFIX = env_str("GCS_AUDIT_ARCHIVE_PREFIX", "compliance/audit").strip().rstrip("/")
GCS_REINDEX_PREFIX = env_str("GCS_REINDEX_ARCHIVE_PREFIX", "compliance/reindex").strip().rstrip("/")
SYNC_BATCH_LIMIT = env_int("LOG_SYNC_BATCH_LIMIT", 500, minimum=10)


def _state_file(name: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{name}.json"


def _load_state(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(path: Path, payload: Mapping[str, object]) -> None:
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        logger.error("Failed to persist sync state %s: %s", path, exc)


def _iter_new_lines(file_path: Path, cursor_state: Dict[str, object]) -> Iterator[Tuple[int, str]]:
    if not file_path.exists():
        return iter(())

    last_offset = int(cursor_state.get("offset", 0) or 0)
    current_size = file_path.stat().st_size
    if last_offset > current_size:
        # File was truncated; start over.
        last_offset = 0

    with file_path.open("r", encoding="utf-8") as handle:
        handle.seek(last_offset)
        while True:
            position = handle.tell()
            line = handle.readline()
            if not line:
                break
            yield position, line.rstrip("\n")


def _parse_json_lines(lines: Iterable[str]) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for raw in lines:
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _archive_to_gcs(records: List[Dict[str, object]], prefix: str, *, kind: str) -> Optional[str]:
    if not records:
        return None
    if not storage_service.is_enabled():
        logger.debug("Storage provider not enabled; skipping %s archive.", kind)
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    object_name = f"{prefix}/{kind}_{timestamp}.jsonl" if prefix else f"{kind}_{timestamp}.jsonl"

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False))
            handle.write("\n")
        temp_path = Path(handle.name)

    try:
        uploaded = storage_service.upload_file(str(temp_path), object_name=object_name, content_type="application/json")
        if uploaded:
            logger.info("Archived %s records to %s.", kind, uploaded)
        return uploaded
    finally:
        try:
            temp_path.unlink(missing_ok=True)  # type: ignore[arg-type]  # py39 compat
        except Exception:
            pass


def _audit_bigquery_schema() -> List["bigquery.SchemaField"]:  # type: ignore[name-defined]
    if bigquery is None:  # pragma: no cover - caller guards on availability
        return []
    return [
        bigquery.SchemaField("timestamp", "TIMESTAMP"),
        bigquery.SchemaField("actor", "STRING"),
        bigquery.SchemaField("action", "STRING"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("payload", "STRING"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ]


def _reindex_bigquery_schema() -> List["bigquery.SchemaField"]:  # type: ignore[name-defined]
    if bigquery is None:  # pragma: no cover
        return []
    return [
        bigquery.SchemaField("timestamp", "TIMESTAMP"),
        bigquery.SchemaField("task_id", "STRING"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("actor", "STRING"),
        bigquery.SchemaField("scope", "STRING"),
        bigquery.SchemaField("scope_detail", "JSON"),
        bigquery.SchemaField("note", "STRING"),
        bigquery.SchemaField("retry_mode", "STRING"),
        bigquery.SchemaField("rag_mode", "STRING"),
        bigquery.SchemaField("queue_id", "STRING"),
        bigquery.SchemaField("queue_wait_ms", "INT64"),
        bigquery.SchemaField("duration_ms", "INT64"),
        bigquery.SchemaField("total_elapsed_ms", "INT64"),

        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ]


def _prepare_audit_rows(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    ingested_at = datetime.now(timezone.utc).isoformat()
    for record in records:
        payload = record.get("payload")
        if payload is None:
            payload_str = ""
        elif isinstance(payload, (dict, list)):
            payload_str = json.dumps(payload, ensure_ascii=False)
        else:
            payload_str = str(payload)
        rows.append(
            {
                "timestamp": record.get("timestamp"),
                "actor": record.get("actor"),
                "action": record.get("action"),
                "source": record.get("source"),
                "payload": payload_str,
                "ingested_at": ingested_at,
            }
        )
    return rows


def _prepare_reindex_rows(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    ingested_at = datetime.now(timezone.utc).isoformat()
    rows: List[Dict[str, object]] = []
    for record in records:
        rows.append(
            {
                "timestamp": record.get("timestamp"),
                "task_id": record.get("taskId"),
                "status": record.get("status"),
                "actor": record.get("actor"),
                "scope": record.get("scope"),
                "scope_detail": record.get("scopeDetail"),
                "note": record.get("note"),
                "retry_mode": record.get("retryMode"),
                "rag_mode": record.get("ragMode"),
                "queue_id": record.get("queueId"),
                "queue_wait_ms": record.get("queueWaitMs"),
                "duration_ms": record.get("durationMs"),
                "total_elapsed_ms": record.get("totalElapsedMs"),

                "ingested_at": ingested_at,
            }
        )
    return rows


def sync_audit_logs(*, archive: bool = True, stream: bool = True) -> Dict[str, object]:
    """Synchronise admin audit logs to GCS and BigQuery."""

    state_path = _state_file("audit_sync")
    state = _load_state(state_path)
    new_lines: List[str] = []
    last_position = None

    for position, line in _iter_new_lines(AUDIT_LOG_PATH, state):
        new_lines.append(line)
        last_position = position
        if len(new_lines) >= SYNC_BATCH_LIMIT:
            break

    records = _parse_json_lines(new_lines)
    result: Dict[str, object] = {
        "rows": len(records),
        "archived": False,
        "bigquery_errors": [],
    }

    if not records:
        return result

    if stream and bigquery_service.is_enabled():
        if bigquery is not None:
            bigquery_service.ensure_table(
                dataset=AUDIT_DATASET,
                table=AUDIT_TABLE,
                schema=_audit_bigquery_schema(),
                partition_field="timestamp",
            )
        rows = _prepare_audit_rows(records)
        errors = bigquery_service.stream_rows(dataset=AUDIT_DATASET, table=AUDIT_TABLE, rows=rows)
        result["bigquery_errors"] = errors

    if archive:
        archive_key = _archive_to_gcs(records, GCS_AUDIT_PREFIX, kind="audit")
        result["archived"] = bool(archive_key)
        if archive_key:
            result["archive_object"] = archive_key

    if last_position is not None:
        state["offset"] = last_position
        _save_state(state_path, state)

    return result


def sync_reindex_logs(*, archive: bool = True, stream: bool = True) -> Dict[str, object]:
    """Synchronise reindex trace history to GCS and BigQuery."""

    state_path = _state_file("reindex_sync")
    state = _load_state(state_path)
    new_lines: List[str] = []
    last_position = None

    for position, line in _iter_new_lines(REINDEX_LOG_PATH, state):
        new_lines.append(line)
        last_position = position
        if len(new_lines) >= SYNC_BATCH_LIMIT:
            break

    records = _parse_json_lines(new_lines)
    result: Dict[str, object] = {
        "rows": len(records),
        "archived": False,
        "bigquery_errors": [],
    }

    if not records:
        return result

    if stream and bigquery_service.is_enabled():
        if bigquery is not None:
            bigquery_service.ensure_table(
                dataset=AUDIT_DATASET,
                table=REINDEX_TABLE,
                schema=_reindex_bigquery_schema(),
                partition_field="timestamp",
            )
        rows = _prepare_reindex_rows(records)
        errors = bigquery_service.stream_rows(dataset=AUDIT_DATASET, table=REINDEX_TABLE, rows=rows)
        result["bigquery_errors"] = errors

    if archive:
        archive_key = _archive_to_gcs(records, GCS_REINDEX_PREFIX, kind="reindex")
        result["archived"] = bool(archive_key)
        if archive_key:
            result["archive_object"] = archive_key

    if last_position is not None:
        state["offset"] = last_position
        _save_state(state_path, state)

    return result


__all__ = [
    "sync_audit_logs",
    "sync_reindex_logs",
]
