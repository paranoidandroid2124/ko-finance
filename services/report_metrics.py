"""Prometheus helpers for Event Study export and evidence bundle pipelines."""

from __future__ import annotations

from core.logging import get_logger
from services.prometheus_helpers import build_counter, build_gauge

logger = get_logger(__name__)

_BUNDLE_CLEANUP_COUNTER = build_counter(
    "event_bundle_cleanup_total",
    "Expired event bundle cleanup counts grouped by result.",
    ("result",),
)
_BUNDLE_DIRECTORY_GAUGE = build_gauge(
    "event_bundle_directories",
    "Current number of Event Study bundle directories on disk.",
)
_BUNDLE_RETENTION_GAUGE = build_gauge(
    "event_bundle_retention_days",
    "Retention window (days) configured for Event Study bundles.",
)


def observe_bundle_cleanup(result: str, count: int) -> None:
    """Increment the cleanup counter for ``result`` by ``count``."""

    if _BUNDLE_CLEANUP_COUNTER is None or count <= 0:
        return
    normalized = result or "unknown"
    _BUNDLE_CLEANUP_COUNTER.labels(result=normalized).inc(count)


def set_bundle_directory_count(count: int) -> None:
    """Expose the current number of bundle directories."""

    if _BUNDLE_DIRECTORY_GAUGE is None:
        return
    try:
        _BUNDLE_DIRECTORY_GAUGE.set(float(max(count, 0)))
    except ValueError:
        logger.debug("Failed to set bundle directory gauge: count=%s", count)


def set_bundle_retention_days(days: int) -> None:
    """Emit the configured retention window in days."""

    if _BUNDLE_RETENTION_GAUGE is None:
        return
    try:
        _BUNDLE_RETENTION_GAUGE.set(float(max(days, 0)))
    except ValueError:
        logger.debug("Failed to set bundle retention gauge: days=%s", days)


__all__ = [
    "observe_bundle_cleanup",
    "set_bundle_directory_count",
    "set_bundle_retention_days",
]
