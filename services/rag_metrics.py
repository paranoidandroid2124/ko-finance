"""Prometheus helpers for RAG telemetry events."""

from __future__ import annotations

from typing import Optional

from core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore


_EVENT_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]


def _sanitize_label(value: Optional[str], *, default: str) -> str:
    candidate = (value or "").strip().lower()
    if not candidate:
        return default
    return candidate[:64]


if Counter is not None:
    try:
        _EVENT_COUNTER = Counter(
            "rag_telemetry_events_total",
            "Client-side telemetry events for RAG deeplink/viewer interactions.",
            ("event", "source", "reason"),
        )
    except ValueError:
        logger.debug("RAG telemetry metrics already registered; reusing existing collectors.")


def record_event(name: str, *, source: Optional[str] = None, reason: Optional[str] = None) -> None:
    """Increment the telemetry counter for the provided event."""

    if _EVENT_COUNTER is None:
        return
    normalized_event = _sanitize_label(name, default="unknown_event")
    normalized_source = _sanitize_label(source, default="unknown")
    normalized_reason = _sanitize_label(reason, default="none")
    _EVENT_COUNTER.labels(event=normalized_event, source=normalized_source, reason=normalized_reason).inc()


__all__ = ["record_event"]
