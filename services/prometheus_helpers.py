"""Utilities for creating Prometheus collectors with graceful fallbacks."""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

from core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Counter = None  # type: ignore
    Gauge = None  # type: ignore
    Histogram = None  # type: ignore
    REGISTRY = None  # type: ignore


def _lookup_collector(name: str):
    if REGISTRY is None:
        return None
    existing = getattr(REGISTRY, "_names_to_collectors", None)
    if isinstance(existing, dict):
        return existing.get(name)
    return None


def build_counter(name: str, documentation: str, labelnames: Sequence[str] | None = None):
    """Create a Counter while tolerating duplicate registrations."""

    if Counter is None:
        return None
    labels = tuple(labelnames or ())
    try:
        return Counter(name, documentation, labels)
    except ValueError:
        collector = _lookup_collector(name)
        if collector is None:
            logger.debug("Counter %s already registered but not found in registry.", name)
        return collector


def build_gauge(name: str, documentation: str, labelnames: Sequence[str] | None = None):
    """Create a Gauge while tolerating duplicate registrations."""

    if Gauge is None:
        return None
    labels = tuple(labelnames or ())
    try:
        return Gauge(name, documentation, labels)
    except ValueError:
        collector = _lookup_collector(name)
        if collector is None:
            logger.debug("Gauge %s already registered but not found in registry.", name)
        return collector


def build_histogram(name: str, documentation: str, labelnames: Sequence[str] | None = None, buckets: Iterable[float] | None = None):
    """Create a Histogram while tolerating duplicate registrations."""

    if Histogram is None:
        return None
    labels = tuple(labelnames or ())
    try:
        return Histogram(name, documentation, labels, buckets=buckets)
    except ValueError:
        collector = _lookup_collector(name)
        if collector is None:
            logger.debug("Histogram %s already registered but not found in registry.", name)
        return collector


__all__ = ["build_counter", "build_gauge", "build_histogram"]
