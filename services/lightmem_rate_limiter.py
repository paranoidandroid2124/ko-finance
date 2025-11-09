"""Redis-backed rate limiter utilities for LightMem-related workloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from core.env import env_int, env_str
from core.logging import get_logger
from services import metrics, notification_service

try:  # pragma: no cover - optional dependency in some environments
    import redis  # type: ignore
except ImportError:  # pragma: no cover - redis might be absent in tests
    redis = None  # type: ignore

logger = get_logger(__name__)

_REDIS_URL = env_str("LIGHTMEM_RATE_LIMIT_REDIS_URL") or env_str("LIGHTMEM_REDIS_URL")
_ALERT_WEBHOOK = env_str("LIGHTMEM_RATE_LIMIT_SLACK_WEBHOOK")
_ALERT_COOLDOWN_SECONDS = env_int("LIGHTMEM_RATE_LIMIT_ALERT_COOLDOWN_SECONDS", 300, minimum=60)
_CLIENT: Optional["redis.Redis"] = None  # type: ignore[name-defined]
_CLIENT_ERROR_LOGGED = False
_LAST_ALERT: Dict[str, datetime] = {}


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate limit evaluation."""

    allowed: bool
    remaining: Optional[int]
    reset_at: Optional[datetime]
    backend_error: bool = False


def _get_client() -> Optional["redis.Redis"]:  # type: ignore[name-defined]
    global _CLIENT, _CLIENT_ERROR_LOGGED  # pylint: disable=global-statement
    if _CLIENT is not None:
        return _CLIENT
    if not _REDIS_URL or redis is None:
        return None
    try:
        _CLIENT = redis.Redis.from_url(_REDIS_URL, decode_responses=False)
    except Exception as exc:  # pragma: no cover - defensive logging
        if not _CLIENT_ERROR_LOGGED:
            logger.warning("LightMem rate limiter Redis init failed: %s", exc)
            _CLIENT_ERROR_LOGGED = True
        _CLIENT = None
    return _CLIENT


def check_limit(
    scope: str,
    identifier: Optional[str],
    *,
    limit: int,
    window_seconds: int = 60,
    weight: int = 1,
) -> RateLimitResult:
    """Increment the bucket for ``(scope, identifier)`` and verify the allowance."""

    if limit <= 0 or window_seconds <= 0 or weight <= 0:
        return RateLimitResult(allowed=True, remaining=None, reset_at=None)

    client = _get_client()
    if client is None:
        return RateLimitResult(allowed=True, remaining=None, reset_at=None, backend_error=True)

    key = f"rl:{scope}:{identifier or 'global'}"
    try:
        pipeline = client.pipeline()
        pipeline.incrby(key, weight)
        pipeline.ttl(key)
        count, ttl = pipeline.execute()
        if ttl is None or ttl < 0:
            client.expire(key, window_seconds)
            ttl = window_seconds
        allowed = int(count) <= limit
        remaining = max(limit - int(count), 0)
        reset_at = datetime.now(timezone.utc) + timedelta(seconds=max(int(ttl), 0))
        metrics.record_rate_limit(scope, allowed)
        metrics.record_rate_limit_remaining(scope, remaining)
        result = RateLimitResult(allowed=allowed, remaining=remaining, reset_at=reset_at)
        if not allowed:
            _maybe_send_alert(scope, identifier, remaining, limit, reset_at)
        return result
    except Exception as exc:  # pragma: no cover - network/redis issues
        logger.warning("LightMem rate limiter failed for %s:%s - %s", scope, identifier, exc, exc_info=True)
        return RateLimitResult(allowed=True, remaining=None, reset_at=None, backend_error=True)


def _maybe_send_alert(
    scope: str,
    identifier: Optional[str],
    remaining: int,
    limit: int,
    reset_at: Optional[datetime],
) -> None:
    if not _ALERT_WEBHOOK:
        return
    now = datetime.now(timezone.utc)
    last_sent = _LAST_ALERT.get(scope)
    if last_sent and (now - last_sent).total_seconds() < _ALERT_COOLDOWN_SECONDS:
        return
    target = identifier or "global"
    summary = (
        f"Scope: {scope} · Identifier: {target} · Remaining: {remaining}/{limit} · "
        f"Resets: {reset_at.isoformat() if reset_at else 'unknown'}"
    )
    message = (
        ":rotating_light: *LightMem rate limit hit*\n"
        f"- Scope: `{scope}`\n"
        f"- Identifier: `{target}`\n"
        f"- Remaining: `{remaining}` / `{limit}`\n"
        f"- Resets: `{reset_at.isoformat() if reset_at else 'unknown'}`"
    )
    try:
        notification_service.dispatch_notification(
            "slack",
            message,
            targets=[_ALERT_WEBHOOK],
            metadata={"headline": "LightMem rate limit triggered", "summary": summary},
        )
        _LAST_ALERT[scope] = now
    except Exception as exc:  # pragma: no cover - best-effort alerting
        logger.warning("Failed to dispatch LightMem rate limit alert: %s", exc, exc_info=True)


__all__ = ["RateLimitResult", "check_limit"]
