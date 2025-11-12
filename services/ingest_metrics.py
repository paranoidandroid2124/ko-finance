"""Prometheus helpers dedicated to ingest health tracking."""

from __future__ import annotations

import time
from typing import Optional

from core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Gauge, Histogram  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore
    Gauge = None  # type: ignore
    Histogram = None  # type: ignore

_RESULT_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]
_ERROR_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]
_RETRY_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]
_LATENCY_HISTOGRAM: Optional["Histogram"] = None  # type: ignore[name-defined]
_BACKFILL_HISTOGRAM: Optional["Histogram"] = None  # type: ignore[name-defined]
_LAST_SUCCESS_GAUGE: Optional["Gauge"] = None  # type: ignore[name-defined]
_LAST_ERROR_GAUGE: Optional["Gauge"] = None  # type: ignore[name-defined]
_DLQ_GAUGE: Optional["Gauge"] = None  # type: ignore[name-defined]

_LATENCY_BUCKETS = (
    0.5,
    1.0,
    2.0,
    5.0,
    10.0,
    30.0,
    60.0,
    120.0,
    300.0,
    600.0,
    900.0,
)
_BACKFILL_BUCKETS = (
    60.0,
    120.0,
    300.0,
    600.0,
    1200.0,
    1800.0,
    2700.0,
    3600.0,
    5400.0,
    7200.0,
)

if Counter is not None and Gauge is not None and Histogram is not None:
    try:
        _RESULT_COUNTER = Counter(
            "ingest_pipeline_result_total",
            "Ingest pipeline outcomes per stage.",
            ("stage", "result"),
        )
        _ERROR_COUNTER = Counter(
            "ingest_pipeline_errors_total",
            "Ingest failures grouped by stage, source, and exception.",
            ("stage", "source", "exception"),
        )
        _RETRY_COUNTER = Counter(
            "ingest_pipeline_retries_total",
            "Celery retries triggered for ingest tasks.",
            ("task",),
        )
        _LATENCY_HISTOGRAM = Histogram(
            "ingest_pipeline_latency_seconds",
            "Latency distribution for ingest stages.",
            ("stage",),
            buckets=_LATENCY_BUCKETS,
        )
        _BACKFILL_HISTOGRAM = Histogram(
            "ingest_backfill_duration_seconds",
            "Duration of ingest backfill commands.",
            buckets=_BACKFILL_BUCKETS,
        )
        _LAST_SUCCESS_GAUGE = Gauge(
            "ingest_pipeline_last_success_timestamp",
            "Unix timestamp of the last successful ingest stage execution.",
            ("stage",),
        )
        _LAST_ERROR_GAUGE = Gauge(
            "ingest_pipeline_last_error_timestamp",
            "Unix timestamp of the last ingest failure per stage.",
            ("stage",),
        )
        _DLQ_GAUGE = Gauge(
            "ingest_dlq_entries",
            "Number of DLQ entries grouped by status.",
            ("status",),
        )
    except ValueError:  # pragma: no cover - duplicate registration on reload
        logger.debug("Ingest metrics already registered; reusing existing collectors.")


def _now_ts() -> float:
    return float(time.time())


def record_result(stage: str, result: str) -> None:
    if _RESULT_COUNTER is None:
        return
    normalized = result or "unknown"
    _RESULT_COUNTER.labels(stage=stage, result=normalized).inc()
    if normalized == "success" and _LAST_SUCCESS_GAUGE is not None:
        _LAST_SUCCESS_GAUGE.labels(stage=stage).set(_now_ts())
    if normalized in {"failure", "error"} and _LAST_ERROR_GAUGE is not None:
        _LAST_ERROR_GAUGE.labels(stage=stage).set(_now_ts())


def record_error(stage: str, source: str, exception: Exception | str) -> None:
    if _ERROR_COUNTER is None:
        return
    if isinstance(exception, Exception):
        exc_name = exception.__class__.__name__
    else:
        exc_name = str(exception) or "UnknownError"
    _ERROR_COUNTER.labels(stage=stage, source=source or "unknown", exception=exc_name).inc()
    if _LAST_ERROR_GAUGE is not None:
        _LAST_ERROR_GAUGE.labels(stage=stage).set(_now_ts())


def observe_latency(stage: str, seconds: float) -> None:
    if _LATENCY_HISTOGRAM is None or seconds < 0:
        return
    _LATENCY_HISTOGRAM.labels(stage=stage).observe(seconds)


def record_retry(task_name: str) -> None:
    if _RETRY_COUNTER is None:
        return
    _RETRY_COUNTER.labels(task=task_name).inc()


def set_dlq_size(status: str, count: int) -> None:
    if _DLQ_GAUGE is None:
        return
    try:
        _DLQ_GAUGE.labels(status=status).set(float(max(0, count)))
    except ValueError:
        logger.debug("Failed to set DLQ gauge for status=%s count=%s", status, count)


def observe_backfill_duration(seconds: float) -> None:
    if _BACKFILL_HISTOGRAM is None or seconds < 0:
        return
    _BACKFILL_HISTOGRAM.observe(seconds)


__all__ = [
    "record_result",
    "record_error",
    "observe_latency",
    "record_retry",
    "set_dlq_size",
    "observe_backfill_duration",
]

