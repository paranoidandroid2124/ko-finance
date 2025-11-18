"""Persistence helpers for administrator-managed RAG configuration."""

from __future__ import annotations

import difflib
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Mapping, Sequence, cast

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
from services.notification_service import NotificationResult, dispatch_notification

logger = get_logger(__name__)

_ADMIN_DIR = ADMIN_BASE_DIR
_RAG_CONFIG_PATH = _ADMIN_DIR / "rag_config.json"
_RAG_HISTORY_PATH = _ADMIN_DIR / "rag_reindex.jsonl"
_RAG_RETRY_QUEUE_PATH = _ADMIN_DIR / "rag_reindex_retry.json"

AUTO_RETRY_MAX_ATTEMPTS = env_int("ADMIN_RAG_AUTO_RETRY_MAX_ATTEMPTS", default=3)
AUTO_RETRY_COOLDOWN_MINUTES = env_int("ADMIN_RAG_AUTO_RETRY_COOLDOWN_MINUTES", default=30)
REINDEX_SLA_MINUTES = env_int("ADMIN_RAG_REINDEX_SLA_MINUTES", default=30, minimum=1)
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


def _format_duration_ms(value: Optional[int]) -> str:
    if value is None:
        return "-"
    seconds_total = value / 1000.0
    if seconds_total < 1:
        return f"{value}ms"
    if seconds_total < 60:
        return f"{seconds_total:.1f}s"
    minutes, seconds = divmod(int(seconds_total), 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s"


def handle_reindex_sla_breach(
    *,
    task_id: str,
    actor: str,
    scope: str,
    scope_detail: Optional[Iterable[str]],
    total_elapsed_ms: int,
    duration_ms: Optional[int],
    queue_wait_ms: Optional[int],
    retry_mode: Optional[str],
    queue_id: Optional[str],
    note: Optional[str],
    langfuse_trace_url: Optional[str],
    langfuse_trace_id: Optional[str],
    langfuse_span_id: Optional[str],
) -> NotificationResult:
    sla_target_ms = REINDEX_SLA_MINUTES * 60 * 1000
    scope_items = list(scope_detail) if scope_detail else []
    scope_label = scope or "all"
    elapsed_label = _format_duration_ms(total_elapsed_ms)
    duration_label = _format_duration_ms(duration_ms)
    queue_label = _format_duration_ms(queue_wait_ms)

    message = (
        f"RAG 재색인 SLA {REINDEX_SLA_MINUTES}분 초과 :: {scope_label} "
        f"(총 소요 {elapsed_label}, 처리 {duration_label}, 대기 {queue_label})"
    )
    markdown_lines = [
        "*RAG 재색인 SLA 초과 감지*",
        f"- 범위: `{scope_label}`",
        f"- 총 소요: {elapsed_label} (목표 {REINDEX_SLA_MINUTES}분)",
        f"- 처리 시간: {duration_label}",
        f"- 큐 대기: {queue_label}",
    ]
    if retry_mode:
        markdown_lines.append(f"- Retry 모드: `{retry_mode}`")
    if langfuse_trace_url:
        markdown_lines.append(f"- Trace: {langfuse_trace_url}")

    attachment_fields = [
        {"title": "Task ID", "value": task_id, "short": True},
        {"title": "Scope", "value": scope_label, "short": True},
        {"title": "Actor", "value": actor or "system", "short": True},
        {"title": "총 소요", "value": f"{elapsed_label} / 목표 {REINDEX_SLA_MINUTES}분", "short": False},
        {"title": "처리 시간", "value": duration_label, "short": True},
        {"title": "큐 대기", "value": queue_label, "short": True},
    ]
    if queue_id:
        attachment_fields.append({"title": "Queue ID", "value": queue_id, "short": True})
    if retry_mode:
        attachment_fields.append({"title": "Retry Mode", "value": retry_mode, "short": True})
    if scope_items:
        attachment_fields.append({"title": "Scope Detail", "value": ", ".join(scope_items), "short": False})
    if langfuse_trace_url:
        attachment_fields.append({"title": "Trace URL", "value": langfuse_trace_url, "short": False})
    elif langfuse_trace_id:
        attachment_fields.append({"title": "Trace ID", "value": langfuse_trace_id, "short": True})
    if langfuse_span_id:
        attachment_fields.append({"title": "Span ID", "value": langfuse_span_id, "short": True})
    if note:
        trimmed_note = note if len(note) <= 280 else f"{note[:277]}..."
        attachment_fields.append({"title": "Note", "value": trimmed_note, "short": False})

    metadata = {
        "subject": "[RAG] 재색인 SLA 초과",
        "markdown": "\n".join(markdown_lines),
        "attachments": [
            {
                "color": "#f97316",
                "title": "재색인 SLA 자동 대응",
                "fields": attachment_fields,
                "footer": "K-Finance Admin · SLA Guard",
            }
        ],
    }

    try:
        dispatch_result = dispatch_notification("slack", message, metadata=metadata)
    except Exception as exc:  # pragma: no cover - notification best effort
        logger.error("Failed to dispatch SLA breach notification: %s", exc, exc_info=True)
        dispatch_result = NotificationResult(status="failed", error=str(exc))

    append_audit_log(
        filename="rag_audit.jsonl",
        actor=actor,
        action="rag_reindex_sla_breach",
        payload={
            "taskId": task_id,
            "scope": scope,
            "scopeDetail": scope_items or None,
            "totalElapsedMs": total_elapsed_ms,
            "durationMs": duration_ms,
            "queueWaitMs": queue_wait_ms,
            "slaTargetMs": sla_target_ms,
            "retryMode": retry_mode,
            "queueId": queue_id,
            "note": note,
            "langfuseTraceUrl": langfuse_trace_url,
            "langfuseTraceId": langfuse_trace_id,
            "langfuseSpanId": langfuse_span_id,
            "notificationStatus": dispatch_result.status,
            "notificationError": dispatch_result.error,
        },
    )
    if dispatch_result.error:
        logger.warning(
            "SLA breach notification status=%s task_id=%s error=%s",
            dispatch_result.status,
            task_id,
            dispatch_result.error,
        )
    else:
        logger.info(
            "SLA breach notification dispatched for task_id=%s status=%s",
            task_id,
            dispatch_result.status,
        )
    return dispatch_result


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
    queued_at: Optional[str] = None,
    queue_wait_ms: Optional[int] = None,
    total_elapsed_ms: Optional[int] = None,
    event_brief_path: Optional[str] = None,
    event_brief_object: Optional[str] = None,
    event_brief_url: Optional[str] = None,
    evidence_package_path: Optional[str] = None,
    evidence_package_object: Optional[str] = None,
    evidence_package_url: Optional[str] = None,
    evidence_manifest_path: Optional[str] = None,
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
    if queued_at:
        record["queuedAt"] = queued_at
    if queue_wait_ms is not None:
        record["queueWaitMs"] = int(queue_wait_ms)
    if total_elapsed_ms is not None:
        record["totalElapsedMs"] = int(total_elapsed_ms)
    if event_brief_path:
        record["eventBriefPath"] = event_brief_path
    if event_brief_object:
        record["eventBriefObject"] = event_brief_object
    if event_brief_url:
        record["eventBriefUrl"] = event_brief_url
    if evidence_package_path:
        record["evidencePackagePath"] = evidence_package_path
    if evidence_package_object:
        record["evidencePackageObject"] = evidence_package_object
    if evidence_package_url:
        record["evidencePackageUrl"] = evidence_package_url
    if evidence_manifest_path:
        record["evidenceManifestPath"] = evidence_manifest_path
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
    def _retry_sort_key(entry: Mapping[str, Any]) -> str:
        raw_value = entry.get("updatedAt") or entry.get("createdAt")
        return raw_value if isinstance(raw_value, str) else ""

    entries.sort(key=_retry_sort_key, reverse=True)
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
        attempts = _coerce_int(entry.get("attempts")) or 0
        if attempts >= max_attempts:
            continue
        last_attempt_raw = entry.get("lastAttemptAt")
        last_attempt_at = parse_iso_datetime(last_attempt_raw if isinstance(last_attempt_raw, str) else None)
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
    last_attempt_raw = entry.get("lastAttemptAt")
    last_attempt_at = parse_iso_datetime(last_attempt_raw if isinstance(last_attempt_raw, str) else None)
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


def compute_retry_entry_age(entry: Mapping[str, Any], *, now: Optional[datetime] = None) -> Optional[int]:
    reference = now or datetime.now(timezone.utc)
    candidate_times: List[datetime] = []
    for field in ("lastAttemptAt", "createdAt", "updatedAt"):
        raw_value = entry.get(field)
        parsed = parse_iso_datetime(raw_value if isinstance(raw_value, str) else None)
        if parsed:
            candidate_times.append(parsed)
    if not candidate_times:
        return None
    earliest = min(candidate_times)
    delta = reference - earliest
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds() * 1000)


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


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            numeric = float(stripped)
        except ValueError:
            return None
    else:
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return int(numeric)


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            numeric = float(stripped)
        except ValueError:
            return None
    else:
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _first_non_empty(payload: Mapping[str, Any], keys: Sequence[str]) -> Optional[str]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _extract_pdf_rect(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    rect: Dict[str, Any] = {}
    page = _coerce_int(value.get("page"))
    if page is not None:
        rect["page"] = page
    for key in ("x", "y", "width", "height"):
        numeric = _coerce_float(value.get(key))
        if numeric is not None:
            rect[key] = numeric
    return rect or None


def _extract_anchor(payload: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    raw_anchor = payload.get("anchor") or payload.get("anchor_meta") or payload.get("anchorMeta")
    if not isinstance(raw_anchor, Mapping):
        return None

    result: Dict[str, Any] = {}
    paragraph = raw_anchor.get("paragraphId") or raw_anchor.get("paragraph_id")
    if isinstance(paragraph, str) and paragraph.strip():
        result["paragraphId"] = paragraph.strip()
    elif paragraph is not None:
        result["paragraphId"] = str(paragraph)

    rect = _extract_pdf_rect(raw_anchor.get("pdfRect") or raw_anchor.get("pdf_rect"))
    if rect:
        result["pdfRect"] = rect

    similarity = _coerce_float(raw_anchor.get("similarity"))
    if similarity is not None:
        result["similarity"] = max(0.0, min(1.0, similarity))

    return result or None


def _extract_self_check(payload: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    raw = payload.get("self_check") or payload.get("selfCheck")
    if not isinstance(raw, Mapping):
        return None
    result: Dict[str, Any] = {}
    score = _coerce_float(raw.get("score"))
    if score is not None:
        result["score"] = max(0.0, min(1.0, score))
    verdict = raw.get("verdict")
    if isinstance(verdict, str):
        normalized = verdict.strip().lower()
        if normalized in {"pass", "warn", "fail"}:
            result["verdict"] = normalized
    explanation = raw.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        result["explanation"] = explanation.strip()
    return result or None


def _extract_reliability(payload: Mapping[str, Any]) -> Optional[str]:
    value = payload.get("source_reliability") or payload.get("sourceReliability")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"high", "medium", "low"}:
            return normalized
    return None


def _extract_urls(payload: Mapping[str, Any]) -> Dict[str, str]:
    urls: Dict[str, str] = {}
    document_url = _first_non_empty(
        payload,
        (
            "documentUrl",
            "document_url",
            "viewerUrl",
            "viewer_url",
            "sourceUrl",
            "source_url",
            "pdfUrl",
            "pdf_url",
        ),
    )
    if document_url:
        urls["documentUrl"] = document_url

    viewer_url = _first_non_empty(payload, ("viewerUrl", "viewer_url"))
    if viewer_url:
        urls["viewerUrl"] = viewer_url

    download_url = _first_non_empty(payload, ("downloadUrl", "download_url"))
    if download_url:
        urls["downloadUrl"] = download_url

    source_url = _first_non_empty(payload, ("sourceUrl", "source_url"))
    if source_url and source_url != urls.get("documentUrl"):
        urls["sourceUrl"] = source_url

    return urls


def collect_evidence_diff(
    *,
    started_at: datetime,
    finished_at: Optional[datetime],
    scope_detail: Optional[Iterable[str]],
    langfuse_trace_url: Optional[str] = None,
    langfuse_trace_id: Optional[str] = None,
    langfuse_span_id: Optional[str] = None,
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
        payload_raw = cast(Any, snapshot.payload)
        payload: Dict[str, Any] = payload_raw if isinstance(payload_raw, dict) else {}
        urn_value = cast(Optional[str], cast(Any, snapshot.urn_id))
        snapshot_hash = cast(Optional[str], cast(Any, snapshot.snapshot_hash))
        cache_key = (urn_value or "", snapshot_hash or "")
        snapshot_cache[cache_key] = payload

        source_value = str(payload.get("source") or payload.get("source_name") or "").strip().lower()
        if apply_filter and source_value not in scope_filter:
            continue

        diff_type = str(cast(Optional[str], cast(Any, snapshot.diff_type)) or "").lower()
        previous_payload: Dict[str, Any] = {}
        previous_hash = cast(Optional[str], cast(Any, snapshot.previous_snapshot_hash))
        if previous_hash:
            previous_key = (cache_key[0], previous_hash)
            previous_payload = snapshot_cache.get(previous_key, {})
            if not previous_payload:
                try:
                    previous_snapshot = session.get(EvidenceSnapshot, previous_key)
                except Exception:
                    previous_snapshot = None
                if previous_snapshot is not None:
                    previous_payload_raw = cast(Any, previous_snapshot.payload)
                    previous_payload = (
                        previous_payload_raw if isinstance(previous_payload_raw, dict) else {}
                    )
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

        urn_id = cache_key[0]
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

        page_number = _coerce_int(visible_payload.get("pageNumber") or visible_payload.get("page_number"))
        previous_page_number = (
            _coerce_int(previous_payload.get("pageNumber") or previous_payload.get("page_number"))
            if previous_payload
            else None
        )
        if page_number is None and previous_page_number is not None:
            page_number = previous_page_number

        reliability = _extract_reliability(visible_payload)
        previous_reliability = _extract_reliability(previous_payload) if previous_payload else None

        anchor = _extract_anchor(visible_payload)
        previous_anchor = _extract_anchor(previous_payload) if previous_payload else None

        self_check = _extract_self_check(visible_payload)
        previous_self_check = _extract_self_check(previous_payload) if previous_payload else None

        url_fields = _extract_urls(visible_payload)

        previous_quote_value: Optional[str] = None
        if previous_payload:
            prev_quote_candidate = previous_payload.get("quote") or previous_payload.get("content")
            if isinstance(prev_quote_candidate, str) and prev_quote_candidate.strip():
                previous_quote_value = prev_quote_candidate

        previous_section_value: Optional[str] = None
        if previous_payload:
            prev_section_candidate = previous_payload.get("section")
            if isinstance(prev_section_candidate, str) and prev_section_candidate.strip():
                previous_section_value = prev_section_candidate

        updated_at_value = cast(Optional[datetime], cast(Any, snapshot.updated_at))
        sample_entry: Dict[str, Any] = {
            "urnId": urn_id or None,
            "diffType": diff_type,
            "source": visible_payload.get("source"),
            "section": visible_payload.get("section"),
            "quote": quote_text,
            "chunkId": visible_payload.get("chunk_id") or visible_payload.get("id"),
            "updatedAt": updated_at_value.isoformat() if updated_at_value else None,
        }
        if diff_changes:
            sample_entry["changes"] = diff_changes
            changed_fields = [change.get("field") for change in diff_changes if change.get("field")]
            if changed_fields:
                sample_entry["diffChangedFields"] = changed_fields
        if page_number is not None:
            sample_entry["pageNumber"] = page_number
        if previous_page_number is not None and previous_page_number != sample_entry.get("pageNumber"):
            sample_entry["previousPageNumber"] = previous_page_number
        if reliability:
            sample_entry["sourceReliability"] = reliability
        if previous_reliability:
            sample_entry["previousSourceReliability"] = previous_reliability
        if anchor:
            sample_entry["anchor"] = anchor
        if previous_anchor:
            sample_entry["previousAnchor"] = previous_anchor
        if self_check:
            sample_entry["selfCheck"] = self_check
        if previous_self_check:
            sample_entry["previousSelfCheck"] = previous_self_check
        if url_fields:
            sample_entry.update(url_fields)
        if previous_quote_value and (diff_type == "removed" or previous_quote_value != sample_entry.get("quote")):
            sample_entry["previousQuote"] = previous_quote_value
        if previous_section_value and (
            diff_type == "removed" or previous_section_value != sample_entry.get("section")
        ):
            sample_entry["previousSection"] = previous_section_value
        if langfuse_trace_url:
            sample_entry["langfuseTraceUrl"] = langfuse_trace_url
        if langfuse_trace_id:
            sample_entry["langfuseTraceId"] = langfuse_trace_id
        if langfuse_span_id:
            sample_entry["langfuseSpanId"] = langfuse_span_id

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
            "p50DurationMs": None,
            "p95DurationMs": None,
            "p50QueueWaitMs": None,
            "p95QueueWaitMs": None,
            "slaTargetMs": REINDEX_SLA_MINUTES * 60 * 1000,
            "slaBreaches": 0,
            "slaMet": 0,
        }

    completed = sum(1 for item in items if str(item.get("status") or "").lower() == "completed")
    failed = sum(1 for item in items if str(item.get("status") or "").lower() == "failed")
    traced_urls = [
        value for value in (item.get("langfuseTraceUrl") for item in items) if isinstance(value, str)
    ]
    traced = len(traced_urls)
    durations = [value for value in (_coerce_int(item.get("durationMs")) for item in items) if value is not None]
    total_elapsed = [
        value for value in (_coerce_int(item.get("totalElapsedMs")) for item in items) if value is not None
    ]
    queue_waits = [
        value for value in (_coerce_int(item.get("queueWaitMs")) for item in items) if value is not None
    ]
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

    timestamps = [value for value in (item.get("timestamp") for item in items) if isinstance(value, str)]
    last_run_at = max(timestamps) if timestamps else None
    sla_target_ms = REINDEX_SLA_MINUTES * 60 * 1000
    sla_breaches = sum(1 for value in total_elapsed if value > sla_target_ms)
    sla_met = len(total_elapsed) - sla_breaches

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
        "p50DurationMs": _percentile(total_elapsed, 0.50),
        "p95DurationMs": _percentile(total_elapsed, 0.95),
        "p50QueueWaitMs": _percentile(queue_waits, 0.50),
        "p95QueueWaitMs": _percentile(queue_waits, 0.95),
        "slaTargetMs": sla_target_ms,
        "slaBreaches": sla_breaches,
        "slaMet": sla_met,
    }


def _percentile(values: Sequence[int], percentile: float) -> Optional[int]:
    if not values:
        return None
    if len(values) == 1:
        return int(values[0])
    sorted_values = sorted(values)
    bounded = max(0.0, min(1.0, percentile))
    index = (len(sorted_values) - 1) * bounded
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return int(sorted_values[int(index)])
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    interpolated = lower_value + (upper_value - lower_value) * (index - lower)
    return int(round(interpolated))


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
            "oldestQueuedMs": None,
            "averageCooldownRemainingMs": None,
            "slaRiskCount": 0,
        }

    now = datetime.now(timezone.utc)
    ready = 0
    cooling = 0
    auto_mode = 0
    manual_mode = 0
    stalled = 0
    next_auto: Optional[datetime] = None
    oldest_queued: Optional[int] = None
    cooldown_remaining: List[int] = []
    sla_risk = 0
    sla_threshold = timedelta(minutes=REINDEX_SLA_MINUTES)

    for item in items:
        retry_mode = str(item.get("retryMode") or "auto").lower()
        if retry_mode == "auto":
            auto_mode += 1
        else:
            manual_mode += 1

        cooldown_raw = item.get("cooldownUntil")
        cooldown_at = (
            parse_iso_datetime(cooldown_raw if isinstance(cooldown_raw, str) else None) if cooldown_raw else None
        )
        max_attempts = _coerce_int(item.get("maxAttempts")) or AUTO_RETRY_MAX_ATTEMPTS
        attempts = _coerce_int(item.get("attempts")) or 0
        if attempts >= max_attempts:
            stalled += 1

        if cooldown_at and cooldown_at > now:
            cooling += 1
            if retry_mode == "auto" and (next_auto is None or cooldown_at < next_auto):
                next_auto = cooldown_at
            cooldown_remaining.append(int((cooldown_at - now).total_seconds() * 1000))
        else:
            status = str(item.get("status") or "").lower()
            if status in {"queued", "retrying"}:
                ready += 1

        age_ms = compute_retry_entry_age(item, now=now)
        if age_ms is not None:
            if oldest_queued is None or age_ms > oldest_queued:
                oldest_queued = age_ms
            if timedelta(milliseconds=age_ms) >= sla_threshold:
                sla_risk += 1

    return {
        "totalEntries": total,
        "ready": ready,
        "coolingDown": cooling,
        "autoMode": auto_mode,
        "manualMode": manual_mode,
        "nextAutoRetryAt": next_auto.isoformat() if next_auto else None,
        "stalled": stalled,
        "oldestQueuedMs": oldest_queued,
        "averageCooldownRemainingMs": int(sum(cooldown_remaining) / len(cooldown_remaining)) if cooldown_remaining else None,
        "slaRiskCount": sla_risk,
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
    "compute_retry_entry_age",
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
    "handle_reindex_sla_breach",
    "AUTO_RETRY_MAX_ATTEMPTS",
    "AUTO_RETRY_COOLDOWN_MINUTES",
    "REINDEX_SLA_MINUTES",
]
