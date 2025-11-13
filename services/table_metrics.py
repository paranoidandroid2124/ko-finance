"""Prometheus helpers for Table Extraction SLA tracking."""

from __future__ import annotations

from typing import Optional

from core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional metrics dependency
    from prometheus_client import Gauge  # type: ignore
except ImportError:  # pragma: no cover
    Gauge = None  # type: ignore

_SUCCESS_RATE_GAUGE: Optional["Gauge"] = None  # type: ignore[name-defined]
_CELL_ACCURACY_GAUGE: Optional["Gauge"] = None  # type: ignore[name-defined]

if Gauge is not None:
    try:
        _SUCCESS_RATE_GAUGE = Gauge(
            "table_extract_success_rate",
            "Latest ratio of successfully persisted tables per extraction run.",
            ("source",),
        )
        _CELL_ACCURACY_GAUGE = Gauge(
            "table_cell_accuracy",
            "Observed non-empty ratio per table type.",
            ("table_type",),
        )
    except ValueError:
        logger.debug("Table extraction metrics already registered; reusing collectors.")


def record_table_extract_success_ratio(*, stored: int, total: int, source: str = "ingest") -> None:
    if _SUCCESS_RATE_GAUGE is None:
        return
    denominator = max(total, 1)
    ratio = float(max(0, stored)) / float(denominator)
    try:
        _SUCCESS_RATE_GAUGE.labels(source=source or "unknown").set(ratio)
    except ValueError:
        logger.debug("Failed to record success ratio (source=%s stored=%s total=%s).", source, stored, total)


def record_table_cell_accuracy(table_type: str, accuracy: Optional[float]) -> None:
    if _CELL_ACCURACY_GAUGE is None or accuracy is None:
        return
    try:
        _CELL_ACCURACY_GAUGE.labels(table_type=table_type or "unknown").set(float(max(0.0, min(accuracy, 1.0))))
    except ValueError:
        logger.debug("Failed to record cell accuracy (table_type=%s accuracy=%s).", table_type, accuracy)


__all__ = ["record_table_extract_success_ratio", "record_table_cell_accuracy"]
