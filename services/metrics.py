"""Lightweight Prometheus helpers with graceful degradation."""

from __future__ import annotations

from typing import Optional

from core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Gauge  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore
    Gauge = None  # type: ignore

_RATE_LIMIT_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]
_RATE_LIMIT_REMAINING_GAUGE: Optional["Gauge"] = None  # type: ignore[name-defined]

if Counter is not None:
    try:
        _RATE_LIMIT_COUNTER = Counter(
            "lightmem_rate_limit_total",
            "LightMem rate limiter invocations",
            ("scope", "result"),
        )
        _RATE_LIMIT_REMAINING_GAUGE = Gauge(
            "lightmem_rate_limit_remaining",
            "Latest remaining quota for LightMem rate limits.",
            ("scope",),
        )
    except ValueError:
        # Metrics might already be registered if code reloads; log once and continue.
        logger.debug("Prometheus metrics already registered; reusing existing collectors.")


def record_rate_limit(scope: str, allowed: bool) -> None:
    """Increment the rate limit counter for ``scope``."""

    if _RATE_LIMIT_COUNTER is None:
        return
    result = "allowed" if allowed else "blocked"
    _RATE_LIMIT_COUNTER.labels(scope=scope, result=result).inc()


def record_rate_limit_remaining(scope: str, remaining: Optional[int]) -> None:
    """Update the remaining gauge if available."""

    if _RATE_LIMIT_REMAINING_GAUGE is None or remaining is None:
        return
    try:
        _RATE_LIMIT_REMAINING_GAUGE.labels(scope=scope).set(float(remaining))
    except ValueError:
        logger.debug("Failed to set remaining gauge for scope=%s value=%s", scope, remaining)


__all__ = ["record_rate_limit", "record_rate_limit_remaining"]
