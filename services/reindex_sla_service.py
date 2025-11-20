"""BigQuery-powered helpers for Reindex SLA dashboards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from core.env import env_int
from services import bigquery_service
REINDEX_SLA_MINUTES = env_int("ADMIN_RAG_REINDEX_SLA_MINUTES", default=30, minimum=1)
from services.log_sync_service import AUDIT_DATASET, REINDEX_TABLE

try:  # pragma: no cover - optional dependency
    from google.cloud import bigquery  # type: ignore
except ImportError:  # pragma: no cover
    bigquery = None  # type: ignore


SLA_TARGET_MINUTES = REINDEX_SLA_MINUTES
SLA_TARGET_MS = SLA_TARGET_MINUTES * 60 * 1000
DEFAULT_RANGE_DAYS = env_int("ADMIN_RAG_SLA_RANGE_DAYS", 7, minimum=1)
DEFAULT_VIOLATION_LIMIT = env_int("ADMIN_RAG_SLA_VIOLATION_LIMIT", 25, minimum=5)

_PROJECT_ID = bigquery_service.PROJECT_ID
_REINDEX_TABLE_FQN = f"`{_PROJECT_ID}.{AUDIT_DATASET}.{REINDEX_TABLE}`"

_SUMMARY_SQL = f"""
SELECT
  COUNT(*) AS total_runs,
  COUNTIF(status = 'completed') AS completed_runs,
  COUNTIF(status != 'completed') AS failed_runs,
  COUNTIF(total_elapsed_ms > @sla_ms) AS sla_breaches,
  SAFE_DIVIDE(COUNTIF(total_elapsed_ms > @sla_ms), NULLIF(COUNT(*), 0)) AS sla_breach_ratio,
  APPROX_QUANTILES(total_elapsed_ms, 101)[OFFSET(50)] AS p50_total_ms,
  APPROX_QUANTILES(total_elapsed_ms, 101)[OFFSET(95)] AS p95_total_ms,
  APPROX_QUANTILES(queue_wait_ms, 101)[OFFSET(50)] AS p50_queue_ms,
  APPROX_QUANTILES(queue_wait_ms, 101)[OFFSET(95)] AS p95_queue_ms
FROM {_REINDEX_TABLE_FQN}
WHERE timestamp BETWEEN @start_time AND @end_time
"""

_TIMESERIES_SQL = f"""
SELECT
  DATE(timestamp) AS day,
  COUNT(*) AS total_runs,
  COUNTIF(total_elapsed_ms > @sla_ms) AS sla_breaches,
  SAFE_DIVIDE(COUNTIF(total_elapsed_ms > @sla_ms), NULLIF(COUNT(*), 0)) AS sla_breach_ratio,
  APPROX_QUANTILES(total_elapsed_ms, 101)[OFFSET(50)] AS p50_total_ms,
  APPROX_QUANTILES(total_elapsed_ms, 101)[OFFSET(95)] AS p95_total_ms
FROM {_REINDEX_TABLE_FQN}
WHERE timestamp BETWEEN @start_time AND @end_time
GROUP BY day
ORDER BY day ASC
"""

_VIOLATIONS_SQL = f"""
SELECT
  timestamp,
  actor,
  scope,
  scope_detail,
  note,
  status,
  retry_mode,
  rag_mode,
  queue_id,
  queue_wait_ms,
  total_elapsed_ms,
  langfuse_trace_url,
  langfuse_trace_id,
  langfuse_span_id
FROM {_REINDEX_TABLE_FQN}
WHERE timestamp BETWEEN @start_time AND @end_time
  AND total_elapsed_ms > @sla_ms
ORDER BY timestamp DESC
LIMIT @limit
"""


def _ensure_bigquery() -> None:
    if not bigquery_service.is_enabled() or bigquery is None or not _PROJECT_ID:
        raise RuntimeError("BigQuery is not configured for SLA reporting.")


def _to_scalar_params(items: Iterable[bigquery.ScalarQueryParameter]) -> Sequence[bigquery.ScalarQueryParameter]:
    return list(items)


def _bq_param(name: str, type_: str, value: Any) -> "bigquery.ScalarQueryParameter":  # type: ignore[name-defined]
    return bigquery.ScalarQueryParameter(name, type_, value)  # type: ignore[call-arg]


def _convert_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _convert_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: _convert_value(value) for key, value in row.items()}


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except Exception:
        return 0


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int):
        return float(value)
    try:
        return float(value)
    except Exception:
        return 0.0


def _to_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(value)
    except Exception:
        return None

def fetch_reindex_sla_summary(
    *,
    range_days: int = DEFAULT_RANGE_DAYS,
    violation_limit: int = DEFAULT_VIOLATION_LIMIT,
) -> Dict[str, Any]:
    """Return summary statistics, daily trends, and recent SLA violations."""

    _ensure_bigquery()

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=range_days)

    summary_params = _to_scalar_params(
        [
            _bq_param("sla_ms", "INT64", SLA_TARGET_MS),
            _bq_param("start_time", "TIMESTAMP", start),
            _bq_param("end_time", "TIMESTAMP", now),
        ]
    )

    summary_rows = bigquery_service.run_query(_SUMMARY_SQL, parameters=summary_params)
    summary_raw = _convert_row(summary_rows[0]) if summary_rows else {}
    summary = {
        "totalRuns": _to_int(summary_raw.get("total_runs")),
        "completedRuns": _to_int(summary_raw.get("completed_runs")),
        "failedRuns": _to_int(summary_raw.get("failed_runs")),
        "slaBreaches": _to_int(summary_raw.get("sla_breaches")),
        "slaBreachRatio": _to_float(summary_raw.get("sla_breach_ratio")),
        "p50TotalMs": _to_optional_int(summary_raw.get("p50_total_ms")),
        "p95TotalMs": _to_optional_int(summary_raw.get("p95_total_ms")),
        "p50QueueMs": _to_optional_int(summary_raw.get("p50_queue_ms")),
        "p95QueueMs": _to_optional_int(summary_raw.get("p95_queue_ms")),
    }

    timeseries_rows = bigquery_service.run_query(_TIMESERIES_SQL, parameters=summary_params)
    timeseries = []
    for row in timeseries_rows:
        converted = _convert_row(row)
        day_value = converted.get("day")
        day_str = day_value.isoformat() if hasattr(day_value, "isoformat") else str(day_value)
        timeseries.append(
            {
                "day": day_str,
                "totalRuns": _to_int(converted.get("total_runs")),
                "slaBreaches": _to_int(converted.get("sla_breaches")),
                "slaBreachRatio": _to_float(converted.get("sla_breach_ratio")),
                "p50TotalMs": _to_optional_int(converted.get("p50_total_ms")),
                "p95TotalMs": _to_optional_int(converted.get("p95_total_ms")),
            }
        )

    violation_params = _to_scalar_params(
        [
            _bq_param("sla_ms", "INT64", SLA_TARGET_MS),
            _bq_param("start_time", "TIMESTAMP", start),
            _bq_param("end_time", "TIMESTAMP", now),
            _bq_param("limit", "INT64", violation_limit),
        ]
    )
    violation_rows = bigquery_service.run_query(_VIOLATIONS_SQL, parameters=violation_params)
    recent_violations = []
    for row in violation_rows:
        converted = _convert_row(row)
        detail = converted.get("scope_detail")
        if isinstance(detail, list):
            scope_detail = detail
        elif isinstance(detail, str):
            scope_detail = [part.strip() for part in detail.split(",") if part.strip()]
        else:
            scope_detail = None
        recent_violations.append(
            {
                "timestamp": converted.get("timestamp"),
                "actor": converted.get("actor"),
                "scope": converted.get("scope"),
                "scopeDetail": scope_detail,
                "note": converted.get("note"),
                "status": converted.get("status"),
                "retryMode": converted.get("retry_mode"),
                "ragMode": converted.get("rag_mode"),
                "queueId": converted.get("queue_id"),
                "queueWaitMs": converted.get("queue_wait_ms"),
                "totalElapsedMs": converted.get("total_elapsed_ms"),
                "langfuseTraceUrl": converted.get("langfuse_trace_url"),
                "langfuseTraceId": converted.get("langfuse_trace_id"),
                "langfuseSpanId": converted.get("langfuse_span_id"),
            }
        )

    return {
        "generatedAt": now.isoformat(),
        "rangeDays": range_days,
        "slaTargetMinutes": SLA_TARGET_MINUTES,
        "slaTargetMs": SLA_TARGET_MS,
        "summary": summary,
        "timeseries": timeseries,
        "recentViolations": recent_violations,
    }


__all__ = ["fetch_reindex_sla_summary", "SLA_TARGET_MINUTES"]
