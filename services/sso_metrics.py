"""Prometheus counters for SSO and SCIM activity."""

from __future__ import annotations

from typing import Optional

from core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional dependency
    from prometheus_client import Counter  # type: ignore
except ImportError:  # pragma: no cover
    Counter = None  # type: ignore

_SSO_LOGIN_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]
_SCIM_REQUEST_COUNTER: Optional["Counter"] = None  # type: ignore[name-defined]

if Counter is not None:
    try:
        _SSO_LOGIN_COUNTER = Counter(
            "sso_login_total",
            "Count of SSO login attempts grouped by protocol and provider.",
            ("protocol", "provider", "result"),
        )
        _SCIM_REQUEST_COUNTER = Counter(
            "scim_requests_total",
            "SCIM API calls grouped by provider, resource, and outcome.",
            ("provider", "resource", "method", "result"),
        )
    except ValueError:  # pragma: no cover - already registered
        logger.debug("SSO metrics already registered; reusing existing collectors.")


def record_sso_login(protocol: str, provider_slug: str, success: bool) -> None:
    if _SSO_LOGIN_COUNTER is None:
        return
    result = "success" if success else "failure"
    _SSO_LOGIN_COUNTER.labels(protocol=protocol, provider=provider_slug, result=result).inc()


def record_scim_request(provider_slug: str, resource: str, method: str, success: bool) -> None:
    if _SCIM_REQUEST_COUNTER is None:
        return
    result = "success" if success else "failure"
    _SCIM_REQUEST_COUNTER.labels(provider=provider_slug, resource=resource, method=method.lower(), result=result).inc()


__all__ = ["record_sso_login", "record_scim_request"]
