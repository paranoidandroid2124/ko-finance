"""Prometheus helpers for alert rule compiler + worker health."""

from __future__ import annotations

from typing import Optional

from core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Histogram  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore
    Histogram = None  # type: ignore

_LATENCY_HISTOGRAM: Optional["Histogram"] = None  # type: ignore[name-defined]
_DUPLICATE_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]
_LATENCY_BUCKETS = (
    0.05,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.0,
    5.0,
)

if Histogram is not None and Counter is not None:
    try:
        _LATENCY_HISTOGRAM = Histogram(
            "alert_rule_eval_latency",
            "Seconds spent evaluating an alert rule.",
            ("plan_tier", "result"),
            buckets=_LATENCY_BUCKETS,
        )
        _DUPLICATE_COUNTER = Counter(
            "alert_rule_duplicate_total",
            "Alert rule evaluations skipped because of duplicate payloads.",
            ("plan_tier", "cause"),
        )
    except ValueError:  # pragma: no cover - duplicate registration during reload
        logger.debug("Alert metrics already registered; reusing collectors.")


def observe_rule_latency(plan_tier: str, result: str, seconds: float) -> None:
    if _LATENCY_HISTOGRAM is None or seconds < 0:
        return
    try:
        _LATENCY_HISTOGRAM.labels(plan_tier=plan_tier, result=result or "unknown").observe(seconds)
    except ValueError:  # pragma: no cover - defensive
        logger.debug("Failed to record alert latency (plan=%s result=%s)", plan_tier, result)


def record_duplicate(plan_tier: str, cause: str) -> None:
    if _DUPLICATE_COUNTER is None:
        return
    try:
        _DUPLICATE_COUNTER.labels(plan_tier=plan_tier, cause=cause or "unknown").inc()
    except ValueError:  # pragma: no cover - defensive
        logger.debug("Failed to record duplicate metric (plan=%s cause=%s)", plan_tier, cause)


__all__ = ["observe_rule_latency", "record_duplicate"]

